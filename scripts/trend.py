#!/usr/bin/env python3
"""Scan trend analysis tool.

Tracks storage changes over time and provides insights.

Usage:
    python trend.py [options]
    python trend.py --add scan.json
    python trend.py --show
    python trend.py --chart
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import log, human, get_data_path, load_json, save_json

TREND_FILE = get_data_path("trend_data.json")


def add_scan(scan_file):
    """Add a scan result to trend data."""
    scan_data = load_json(scan_file)
    if not scan_data:
        log("Error: Could not load scan data", "trend")
        return False
    
    system = scan_data.get("system", {})
    groups = scan_data.get("groups", {})
    
    group_totals = {}
    for group, items in groups.items():
        total_kb = sum(item.get("size_kb", 0) for item in items)
        group_totals[group] = {
            "count": len(items),
            "total_kb": total_kb,
            "total_h": human(total_kb)
        }
    
    total_kb = sum(g["total_kb"] for g in group_totals.values())
    
    scan_entry = {
        "timestamp": scan_data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "scan_seconds": scan_data.get("scan_seconds", 0),
        "system": {
            "os": system.get("os", ""),
            "disk_total": system.get("disk_total", ""),
            "disk_used": system.get("disk_used", ""),
            "disk_free": system.get("disk_free", ""),
        },
        "disks": system.get("disks", []),
        "groups": group_totals,
        "total_kb": total_kb,
        "total_h": human(total_kb)
    }
    
    trend_data = load_json(TREND_FILE, {"scans": []})
    trend_data["scans"].append(scan_entry)
    
    # Keep only last 30 scans
    if len(trend_data["scans"]) > 30:
        trend_data["scans"] = trend_data["scans"][-30:]
    
    if save_json(TREND_FILE, trend_data):
        log(f"Added scan to trend data ({len(trend_data['scans'])} scans total)", "trend")
        return True
    
    return False


def show_trend():
    """Show trend analysis."""
    trend_data = load_json(TREND_FILE, {"scans": []})
    scans = trend_data.get("scans", [])
    
    if not scans:
        log("No trend data available. Run a scan first.", "trend")
        return
    
    log(f"Trend data: {len(scans)} scans", "trend")
    log("", "trend")
    
    log("Recent scans:", "trend")
    for scan in scans[-5:]:
        timestamp = scan.get("timestamp", "?")
        total = scan.get("total_h", "?")
        disks = scan.get("disks", [])
        
        disk_info = ""
        for disk in disks:
            disk_info += f" {disk['name']}:{disk['used']}/{disk['total']}"
        
        log(f"  {timestamp}: {total}{disk_info}", "trend")
    
    if len(scans) >= 2:
        log("\nChanges (last 2 scans):", "trend")
        prev = scans[-2]
        curr = scans[-1]
        
        prev_disks = {d["name"]: d for d in prev.get("disks", [])}
        curr_disks = {d["name"]: d for d in curr.get("disks", [])}
        
        for name in set(list(prev_disks.keys()) + list(curr_disks.keys())):
            if name in prev_disks and name in curr_disks:
                prev_used = prev_disks[name]["used"]
                curr_used = curr_disks[name]["used"]
                
                if prev_used != curr_used:
                    log(f"  {name}: {prev_used} -> {curr_used}", "trend")
        
        prev_groups = prev.get("groups", {})
        curr_groups = curr.get("groups", {})
        
        for group in set(list(prev_groups.keys()) + list(curr_groups.keys())):
            if group in prev_groups and group in curr_groups:
                prev_kb = prev_groups[group]["total_kb"]
                curr_kb = curr_groups[group]["total_kb"]
                
                if abs(curr_kb - prev_kb) > 1024:  # > 1MB change
                    diff_kb = curr_kb - prev_kb
                    sign = "+" if diff_kb > 0 else ""
                    log(f"  {group}: {human(prev_kb)} -> {human(curr_kb)} ({sign}{human(abs(diff_kb))})", "trend")


def generate_chart():
    """Generate a simple text-based chart of trends."""
    trend_data = load_json(TREND_FILE, {"scans": []})
    scans = trend_data.get("scans", [])
    
    if len(scans) < 2:
        log("Need at least 2 scans to generate chart.", "trend")
        return
    
    log("Storage usage trend (last 10 scans):", "trend")
    log("", "trend")
    
    recent = scans[-10:]
    max_kb = max(s.get("total_kb", 0) for s in recent)
    if max_kb == 0:
        max_kb = 1
    
    for scan in recent:
        timestamp = scan.get("timestamp", "?")[:10]
        total_kb = scan.get("total_kb", 0)
        total_h = scan.get("total_h", "?")
        
        bar_len = int(total_kb / max_kb * 50)
        bar = "█" * bar_len
        
        log(f"  {timestamp}: {bar} {total_h}", "trend")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scan trend analysis")
    parser.add_argument("--add", type=str, help="Add scan result to trend")
    parser.add_argument("--show", action="store_true", help="Show trend analysis")
    parser.add_argument("--chart", action="store_true", help="Generate text chart")
    parser.add_argument("--clear", action="store_true", help="Clear trend data")
    args = parser.parse_args()
    
    if args.clear:
        if os.path.exists(TREND_FILE):
            os.remove(TREND_FILE)
            log("Trend data cleared.", "trend")
        else:
            log("No trend data to clear.", "trend")
        return
    
    if args.add:
        add_scan(args.add)
    
    if args.show:
        show_trend()
    
    if args.chart:
        generate_chart()
    
    if not any([args.add, args.show, args.chart, args.clear]):
        show_trend()


if __name__ == "__main__":
    main()
