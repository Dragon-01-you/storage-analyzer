#!/usr/bin/env python3
"""File type analysis for storage analyzer.

Scans directories and categorizes files by type (video, image, archive, etc.)
to provide insights into what's consuming disk space.

Usage:
    python file_type_analyzer.py [paths...] [-o output.json]
    python file_type_analyzer.py --top 20
"""
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    log, human, human_bytes, classify_file_type, FILE_TYPE_CATEGORIES,
    get_project_dir, save_json, is_windows
)

DEFAULT_MIN_SIZE_MB = 10  # Only analyze files >= 10MB
DEFAULT_MAX_WORKERS = 6
DEFAULT_TIMEOUT = 120


def scan_file_types(paths, min_size_bytes, max_workers=DEFAULT_MAX_WORKERS, timeout=DEFAULT_TIMEOUT):
    """Scan files and categorize by type."""
    deadline = time.time() + timeout
    
    # Results: category -> {total_bytes, count, files: [...]}
    categories = defaultdict(lambda: {"total_bytes": 0, "count": 0, "files": []})
    
    def _scan_dir(root_path, depth=0):
        local_cats = defaultdict(lambda: {"total_bytes": 0, "count": 0, "files": []})
        if depth > 6 or time.time() > deadline:
            return local_cats
        
        try:
            for entry in os.scandir(root_path):
                if time.time() > deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        if size < min_size_bytes:
                            continue
                        
                        category, label, tier = classify_file_type(entry.path)
                        cat = local_cats[category]
                        cat["total_bytes"] += size
                        cat["count"] += 1
                        # Only keep top files per category (memory efficiency)
                        if len(cat["files"]) < 50:
                            cat["files"].append({
                                "name": entry.name,
                                "path": entry.path,
                                "size_bytes": size,
                                "size_h": human_bytes(size),
                            })
                    elif entry.is_dir(follow_symlinks=False):
                        skip = {".git", "node_modules", "__pycache__", ".svn",
                                "Windows", "WinSxS", "System Volume Information"}
                        if entry.name in skip:
                            continue
                        sub_cats = _scan_dir(entry.path, depth + 1)
                        for cat_name, cat_data in sub_cats.items():
                            local_cats[cat_name]["total_bytes"] += cat_data["total_bytes"]
                            local_cats[cat_name]["count"] += cat_data["count"]
                            # Merge top files
                            existing = local_cats[cat_name]["files"]
                            existing.extend(cat_data["files"])
                            existing.sort(key=lambda x: x["size_bytes"], reverse=True)
                            local_cats[cat_name]["files"] = existing[:50]
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return local_cats
    
    # Parallel scan
    all_cats = defaultdict(lambda: {"total_bytes": 0, "count": 0, "files": []})
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scan_dir, p): p for p in paths if os.path.exists(p)}
        for future in as_completed(futures):
            try:
                path_cats = future.result()
                for cat_name, cat_data in path_cats.items():
                    all_cats[cat_name]["total_bytes"] += cat_data["total_bytes"]
                    all_cats[cat_name]["count"] += cat_data["count"]
                    existing = all_cats[cat_name]["files"]
                    existing.extend(cat_data["files"])
                    existing.sort(key=lambda x: x["size_bytes"], reverse=True)
                    all_cats[cat_name]["files"] = existing[:50]
            except Exception as e:
                log(f"Error scanning: {e}", "filetype")
    
    return all_cats


def format_results(categories):
    """Format results for output."""
    results = []
    
    for cat_name, cat_data in categories.items():
        info = FILE_TYPE_CATEGORIES.get(cat_name, {"label": cat_name, "tier_hint": "yellow"})
        results.append({
            "category": cat_name,
            "label": info.get("label", cat_name),
            "tier_hint": info.get("tier_hint", "yellow"),
            "total_bytes": cat_data["total_bytes"],
            "total_kb": cat_data["total_bytes"] // 1024,
            "total_h": human_bytes(cat_data["total_bytes"]),
            "count": cat_data["count"],
            "top_files": sorted(cat_data["files"], key=lambda x: x["size_bytes"], reverse=True)[:20],
        })
    
    results.sort(key=lambda x: x["total_bytes"], reverse=True)
    return results


def get_default_scan_paths():
    """Get default paths to scan based on platform."""
    paths = []
    home = os.path.expanduser("~")
    paths.append(home)
    
    if is_windows():
        for letter in ("D", "E"):
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                paths.append(drive)
    else:
        for p in ("/home", "/opt", "/var", "/tmp"):
            if os.path.exists(p):
                paths.append(p)
    
    return paths


def main():
    import argparse
    parser = argparse.ArgumentParser(description="File type analysis")
    parser.add_argument("paths", nargs="*", help="Paths to scan (default: home + D: + E:)")
    parser.add_argument("--min-size", type=int, default=DEFAULT_MIN_SIZE_MB,
                        help=f"Min file size in MB (default: {DEFAULT_MIN_SIZE_MB})")
    parser.add_argument("--top", type=int, default=20,
                        help="Show top N files per category")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output JSON file")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Scan timeout in seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()
    
    paths = args.paths if args.paths else get_default_scan_paths()
    min_size_bytes = args.min_size * 1024 * 1024
    
    log(f"Scanning for file types (min size: {args.min_size} MB)...", "filetype")
    log(f"Paths: {paths}", "filetype")
    
    started = time.time()
    categories = scan_file_types(paths, min_size_bytes, timeout=args.timeout)
    elapsed = time.time() - started
    
    results = format_results(categories)
    
    # Summary
    total_bytes = sum(r["total_bytes"] for r in results)
    total_files = sum(r["count"] for r in results)
    
    log(f"\nScan complete in {elapsed:.1f}s", "filetype")
    log(f"Total: {total_files} files, {human_bytes(total_bytes)}", "filetype")
    log("", "filetype")
    
    for r in results:
        pct = (r["total_bytes"] / total_bytes * 100) if total_bytes > 0 else 0
        log(f"  {r['label']:16s}  {r['total_h']:>12s}  {r['count']:>6d} files  ({pct:.1f}%)", "filetype")
    
    output_data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_seconds": round(elapsed, 1),
        "paths_scanned": paths,
        "min_size_mb": args.min_size,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_h": human_bytes(total_bytes),
        "categories": results,
    }
    
    if args.output:
        save_json(args.output, output_data)
        log(f"\nOutput written to {args.output}", "filetype")
    else:
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
