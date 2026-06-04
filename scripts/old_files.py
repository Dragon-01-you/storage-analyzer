#!/usr/bin/env python3
"""Old file detector for storage analyzer.

Finds files that haven't been accessed in a specified number of days,
helping identify stale data that could be archived or deleted.

Usage:
    python old_files.py [paths...] [--days 180] [-o output.json]
    python old_files.py --days 90 --min-size 50
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    log, human_bytes, classify_file_type, get_project_dir,
    save_json, is_windows, is_linux
)

DEFAULT_DAYS = 180
DEFAULT_MIN_SIZE_MB = 50
DEFAULT_MAX_FILES = 200
DEFAULT_TIMEOUT = 120


def find_old_files(paths, days=DEFAULT_DAYS, min_size_bytes=50*1024*1024,
                   max_files=DEFAULT_MAX_FILES, timeout=DEFAULT_TIMEOUT):
    """Find files not accessed in the specified number of days."""
    cutoff = time.time() - (days * 86400)
    deadline = time.time() + timeout
    old_files = []
    
    def _scan(root_path, depth=0):
        results = []
        if depth > 6 or time.time() > deadline:
            return results
        
        try:
            for entry in os.scandir(root_path):
                if time.time() > deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        stat = entry.stat(follow_symlinks=False)
                        # Use the older of atime and mtime
                        last_used = min(stat.st_atime, stat.st_mtime)
                        if last_used < cutoff and stat.st_size >= min_size_bytes:
                            age_days = int((time.time() - last_used) / 86400)
                            category, label, tier = classify_file_type(entry.path)
                            results.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size_bytes": stat.st_size,
                                "size_kb": stat.st_size // 1024,
                                "size_h": human_bytes(stat.st_size),
                                "age_days": age_days,
                                "last_used": datetime.fromtimestamp(last_used).strftime("%Y-%m-%d"),
                                "category": category,
                                "category_label": label,
                                "tier_hint": tier,
                            })
                    elif entry.is_dir(follow_symlinks=False):
                        skip = {".git", "node_modules", "__pycache__", ".svn",
                                "Windows", "WinSxS", "System Volume Information",
                                "System32", "Boot"}
                        if entry.name in skip:
                            continue
                        results.extend(_scan(entry.path, depth + 1))
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return results
    
    for p in paths:
        if not os.path.exists(p):
            log(f"Path not found: {p}", "oldfiles")
            continue
        
        log(f"Scanning {p} for old files (>{days} days)...", "oldfiles")
        old_files.extend(_scan(p))
    
    old_files.sort(key=lambda x: x["size_bytes"], reverse=True)
    return old_files[:max_files]


def get_default_scan_paths():
    """Get default paths to scan."""
    paths = [os.path.expanduser("~")]
    
    if is_windows():
        for letter in ("D", "E"):
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                paths.append(drive)
    else:
        for p in ("/home", "/opt", "/var"):
            if os.path.exists(p):
                paths.append(p)
    
    return paths


def generate_summary(old_files):
    """Generate summary of old files."""
    if not old_files:
        return {"total_files": 0, "total_bytes": 0, "total_h": "0 B", "by_age": {}, "by_category": {}}
    
    total_bytes = sum(f["size_bytes"] for f in old_files)
    
    # Group by age range
    by_age = {
        "6-12 months": {"files": 0, "bytes": 0},
        "1-2 years": {"files": 0, "bytes": 0},
        "2+ years": {"files": 0, "bytes": 0},
    }
    for f in old_files:
        age = f["age_days"]
        if age < 365:
            bucket = "6-12 months"
        elif age < 730:
            bucket = "1-2 years"
        else:
            bucket = "2+ years"
        by_age[bucket]["files"] += 1
        by_age[bucket]["bytes"] += f["size_bytes"]
    
    for bucket in by_age:
        by_age[bucket]["total_h"] = human_bytes(by_age[bucket]["bytes"])
    
    # Group by category
    by_category = {}
    for f in old_files:
        cat = f.get("category", "other")
        if cat not in by_category:
            by_category[cat] = {"label": f.get("category_label", cat), "files": 0, "bytes": 0}
        by_category[cat]["files"] += 1
        by_category[cat]["bytes"] += f["size_bytes"]
    
    for cat in by_category:
        by_category[cat]["total_h"] = human_bytes(by_category[cat]["bytes"])
    
    return {
        "total_files": len(old_files),
        "total_bytes": total_bytes,
        "total_h": human_bytes(total_bytes),
        "by_age": by_age,
        "by_category": by_category,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Old file detector")
    parser.add_argument("paths", nargs="*", help="Paths to scan")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"Days threshold (default: {DEFAULT_DAYS})")
    parser.add_argument("--min-size", type=int, default=DEFAULT_MIN_SIZE_MB,
                        help=f"Min file size in MB (default: {DEFAULT_MIN_SIZE_MB})")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES,
                        help=f"Max results (default: {DEFAULT_MAX_FILES})")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output JSON file")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Scan timeout (default: {DEFAULT_TIMEOUT}s)")
    args = parser.parse_args()
    
    paths = args.paths if args.paths else get_default_scan_paths()
    min_size_bytes = args.min_size * 1024 * 1024
    
    log(f"Searching for files older than {args.days} days (min size: {args.min_size} MB)...", "oldfiles")
    
    started = time.time()
    old_files = find_old_files(paths, args.days, min_size_bytes, args.max_files, args.timeout)
    elapsed = time.time() - started
    
    summary = generate_summary(old_files)
    
    log(f"\nScan complete in {elapsed:.1f}s", "oldfiles")
    log(f"Found {summary['total_files']} old files ({summary['total_h']})", "oldfiles")
    
    if old_files:
        log("\nTop 10 oldest/largest files:", "oldfiles")
        for f in old_files[:10]:
            log(f"  {f['size_h']:>12s}  {f['age_days']:>4d} days  {f['name']}", "oldfiles")
            log(f"               {f['path']}", "oldfiles")
    
    if summary.get("by_age"):
        log("\nBy age:", "oldfiles")
        for bucket, data in summary["by_age"].items():
            if data["files"] > 0:
                log(f"  {bucket:16s}  {data['total_h']:>12s}  {data['files']} files", "oldfiles")
    
    output_data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_seconds": round(elapsed, 1),
        "days_threshold": args.days,
        "min_size_mb": args.min_size,
        "summary": summary,
        "files": old_files,
    }
    
    if args.output:
        save_json(args.output, output_data)
        log(f"\nOutput written to {args.output}", "oldfiles")
    else:
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
