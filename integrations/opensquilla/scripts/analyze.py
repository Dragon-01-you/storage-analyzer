#!/usr/bin/env python3
"""OpenSquilla entrypoint for Storage Analyzer.

Called as a subprocess by OpenSquilla's skill system.
Reads arguments, runs analysis, outputs JSON to stdout.

Usage:
  python analyze.py --path /home/user --depth 3 --min-size 100MB --mode scan
"""
import sys
import os
import json
import argparse
import time

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)


def _parse_size(s: str) -> int:
    """Parse human-readable size string to bytes."""
    s = s.strip().upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            return int(float(s[: -len(suffix)]) * mult)
    return int(s)


def _run_scan(path: str, depth: int, min_size: int) -> dict:
    """Run a full storage scan and return structured results."""
    try:
        from v8.orchestrator import Orchestrator
        from v8.types import ScanConfig

        cfg = ScanConfig(
            roots=[path],
            max_depth=depth,
            min_size=min_size,
        )
        orch = Orchestrator(cfg)
        result = orch.run(dry_run=True)

        return {
            "ok": True,
            "mode": "scan",
            "dry_run": True,
            "disks": _get_disk_info(path),
            "actions": [
                {
                    "act": a.action,
                    "risk": a.risk,
                    "sz": _human_bytes(a.size_bytes),
                    "what": a.reason,
                    "path": a.path,
                }
                for a in (result.proposals or [])[:50]
            ],
            "safe_total": _human_bytes(
                sum(a.size_bytes for a in (result.proposals or []) if a.risk == "SAFE")
            ),
            "elapsed": round(result.elapsed, 2) if hasattr(result, "elapsed") else 0,
        }
    except ImportError:
        return _run_scan_fallback(path, depth, min_size)


def _run_scan_fallback(path: str, depth: int, min_size: int) -> dict:
    """Fallback scanner using engine/ package."""
    try:
        from engine.scanner import HybridScanner

        scanner = HybridScanner()
        items = scanner.scan(path, max_depth=depth, min_size=min_size)
        actions = []
        for item in items[:50]:
            actions.append(
                {
                    "act": "review",
                    "risk": "REVIEW",
                    "sz": _human_bytes(item.get("size", 0)),
                    "what": item.get("name", "unknown"),
                    "path": item.get("path", ""),
                }
            )
        return {
            "ok": True,
            "mode": "scan",
            "dry_run": True,
            "disks": _get_disk_info(path),
            "actions": actions,
            "safe_total": _human_bytes(sum(a.get("size", 0) for a in items)),
            "elapsed": 0,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "mode": "scan"}


def _run_dupes(path: str, min_size: int) -> dict:
    """Run duplicate detection."""
    try:
        from v8.duplicates import DuplicateDetector

        detector = DuplicateDetector()
        groups = detector.find_duplicates(path, min_size=min_size)

        dupes = []
        for group in groups[:20]:
            dupes.append(
                {
                    "keep": group.keep_file,
                    "cnt": len(group.duplicates),
                    "size": _human_bytes(group.total_size),
                    "copies": [d.path for d in group.duplicates[:5]],
                }
            )
        return {
            "ok": True,
            "mode": "dupes",
            "dupes": dupes,
            "total_groups": len(groups),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "mode": "dupes"}


def _get_disk_info(path: str) -> dict:
    """Get disk usage info for the drive containing path."""
    try:
        import shutil

        usage = shutil.disk_usage(path)
        total = usage.total
        used = usage.used
        pct = int(100 * used / total) if total > 0 else 0
        drive = os.path.splitdrive(path)[0] or path
        return {drive: {"p": pct, "uh": _human_bytes(used), "th": _human_bytes(total)}}
    except Exception:
        return {}


def _human_bytes(n: int) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def main():
    parser = argparse.ArgumentParser(description="Storage Analyzer - OpenSquilla Entrypoint")
    parser.add_argument("--path", default=".", help="Directory to analyze")
    parser.add_argument("--depth", type=int, default=3, help="Scan depth (1-10)")
    parser.add_argument("--min-size", default="100MB", help="Minimum file size filter")
    parser.add_argument(
        "--mode",
        choices=["scan", "dupes", "report"],
        default="scan",
        help="Operation mode",
    )
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    min_size = _parse_size(args.min_size)
    depth = max(1, min(10, args.depth))

    start = time.time()

    if args.mode == "dupes":
        result = _run_dupes(path, min_size)
    else:
        result = _run_scan(path, depth, min_size)

    result["elapsed"] = round(time.time() - start, 2)

    # Ensure stdout is UTF-8
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()  # trailing newline


if __name__ == "__main__":
    main()
