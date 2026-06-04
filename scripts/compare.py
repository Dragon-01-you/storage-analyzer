#!/usr/bin/env python3
"""Scan comparison tool.

Compares two scan results and shows differences.

Usage:
    python compare.py <scan1.json> <scan2.json>
    python compare.py <scan1.json> <scan2.json> --format html -o diff.html
"""
import json
import os
import sys
from datetime import datetime

HOME = os.path.expanduser("~")


def log(msg):
    print(f"[compare] {msg}", file=sys.stderr, flush=True)


def human(kb):
    n = float(kb) * 1024
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit not in ("B", "KB") else f"{int(n)} {unit}"
        n /= 1024


def load_scan(filename):
    """Load scan data from file."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_scans(scan1, scan2):
    """Compare two scans and return differences."""
    groups1 = scan1.get("groups", {})
    groups2 = scan2.get("groups", {})
    
    differences = {
        "added": [],
        "removed": [],
        "changed": [],
        "unchanged": []
    }
    
    # Get all group names
    all_groups = set(list(groups1.keys()) + list(groups2.keys()))
    
    for group in all_groups:
        items1 = {item["path"]: item for item in groups1.get(group, [])}
        items2 = {item["path"]: item for item in groups2.get(group, [])}
        
        # Added items
        for path, item in items2.items():
            if path not in items1:
                differences["added"].append({
                    "group": group,
                    "path": path,
                    "name": item.get("name", ""),
                    "size_kb": item.get("size_kb", 0),
                    "size_h": item.get("size_h", human(item.get("size_kb", 0)))
                })
        
        # Removed items
        for path, item in items1.items():
            if path not in items2:
                differences["removed"].append({
                    "group": group,
                    "path": path,
                    "name": item.get("name", ""),
                    "size_kb": item.get("size_kb", 0),
                    "size_h": item.get("size_h", human(item.get("size_kb", 0)))
                })
        
        # Changed items
        for path in set(items1.keys()) & set(items2.keys()):
            item1 = items1[path]
            item2 = items2[path]
            
            size1 = item1.get("size_kb", 0)
            size2 = item2.get("size_kb", 0)
            
            if abs(size2 - size1) > 1024:  # > 1MB change
                differences["changed"].append({
                    "group": group,
                    "path": path,
                    "name": item1.get("name", ""),
                    "size1_kb": size1,
                    "size2_kb": size2,
                    "size1_h": human(size1),
                    "size2_h": human(size2),
                    "diff_kb": size2 - size1,
                    "diff_h": human(abs(size2 - size1))
                })
            else:
                differences["unchanged"].append({
                    "group": group,
                    "path": path,
                    "name": item1.get("name", ""),
                    "size_kb": size1
                })
    
    # Sort by absolute difference
    differences["changed"].sort(key=lambda x: abs(x["diff_kb"]), reverse=True)
    differences["added"].sort(key=lambda x: x["size_kb"], reverse=True)
    differences["removed"].sort(key=lambda x: x["size_kb"], reverse=True)
    
    return differences


def print_comparison(differences, scan1_name, scan2_name):
    """Print comparison results."""
    log("\n" + "=" * 60)
    log(f"Scan Comparison: {scan1_name} vs {scan2_name}")
    log("=" * 60)
    
    # Summary
    added_count = len(differences["added"])
    removed_count = len(differences["removed"])
    changed_count = len(differences["changed"])
    unchanged_count = len(differences["unchanged"])
    
    log(f"\nSummary:")
    log(f"  Added: {added_count} items")
    log(f"  Removed: {removed_count} items")
    log(f"  Changed: {changed_count} items")
    log(f"  Unchanged: {unchanged_count} items")
    
    # Added items
    if differences["added"]:
        log(f"\nAdded ({added_count}):")
        for item in differences["added"][:10]:
            log(f"  + {item['size_h']:>12}  {item['name']} ({item['group']})")
    
    # Removed items
    if differences["removed"]:
        log(f"\nRemoved ({removed_count}):")
        for item in differences["removed"][:10]:
            log(f"  - {item['size_h']:>12}  {item['name']} ({item['group']})")
    
    # Changed items
    if differences["changed"]:
        log(f"\nChanged ({changed_count}):")
        for item in differences["changed"][:10]:
            sign = "+" if item["diff_kb"] > 0 else ""
            log(f"  ~ {item['name']}: {item['size1_h']} -> {item['size2_h']} ({sign}{item['diff_h']})")
    
    log("\n" + "=" * 60)


def save_comparison_html(differences, scan1_name, scan2_name, output_file):
    """Save comparison results as HTML."""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Scan Comparison</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .added {{ background-color: #e8ffe8; }}
        .removed {{ background-color: #ffe8e8; }}
        .changed {{ background-color: #fff8e8; }}
        .size {{ text-align: right; }}
    </style>
</head>
<body>
    <h1>Scan Comparison</h1>
    <p>Comparing: {scan1_name} vs {scan2_name}</p>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <h2>Summary</h2>
    <ul>
        <li>Added: {len(differences['added'])} items</li>
        <li>Removed: {len(differences['removed'])} items</li>
        <li>Changed: {len(differences['changed'])} items</li>
        <li>Unchanged: {len(differences['unchanged'])} items</li>
    </ul>
"""
    
    # Added items
    if differences["added"]:
        html += """
    <h2>Added Items</h2>
    <table>
        <tr><th>Group</th><th>Name</th><th>Path</th><th>Size</th></tr>
"""
        for item in differences["added"]:
            html += f"        <tr class='added'><td>{item['group']}</td><td>{item['name']}</td><td>{item['path']}</td><td class='size'>{item['size_h']}</td></tr>\n"
        html += "    </table>\n"
    
    # Removed items
    if differences["removed"]:
        html += """
    <h2>Removed Items</h2>
    <table>
        <tr><th>Group</th><th>Name</th><th>Path</th><th>Size</th></tr>
"""
        for item in differences["removed"]:
            html += f"        <tr class='removed'><td>{item['group']}</td><td>{item['name']}</td><td>{item['path']}</td><td class='size'>{item['size_h']}</td></tr>\n"
        html += "    </table>\n"
    
    # Changed items
    if differences["changed"]:
        html += """
    <h2>Changed Items</h2>
    <table>
        <tr><th>Group</th><th>Name</th><th>Path</th><th>Before</th><th>After</th><th>Difference</th></tr>
"""
        for item in differences["changed"]:
            sign = "+" if item["diff_kb"] > 0 else ""
            html += f"        <tr class='changed'><td>{item['group']}</td><td>{item['name']}</td><td>{item['path']}</td><td class='size'>{item['size1_h']}</td><td class='size'>{item['size2_h']}</td><td class='size'>{sign}{item['diff_h']}</td></tr>\n"
        html += "    </table>\n"
    
    html += """
</body>
</html>
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    log(f"HTML comparison written to {output_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scan comparison tool")
    parser.add_argument("scan1", help="First scan JSON file")
    parser.add_argument("scan2", help="Second scan JSON file")
    parser.add_argument("--format", choices=["text", "html"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output file (for HTML format)")
    args = parser.parse_args()
    
    # Load scans
    scan1 = load_scan(args.scan1)
    scan2 = load_scan(args.scan2)
    
    # Get scan names
    scan1_name = os.path.basename(args.scan1)
    scan2_name = os.path.basename(args.scan2)
    
    # Compare
    differences = compare_scans(scan1, scan2)
    
    # Output
    if args.format == "html":
        if args.output is None:
            args.output = "comparison.html"
        save_comparison_html(differences, scan1_name, scan2_name, args.output)
    else:
        print_comparison(differences, scan1_name, scan2_name)


if __name__ == "__main__":
    main()
