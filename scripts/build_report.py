#!/usr/bin/env python3
"""Inject an analysis JSON into the HTML template -> a standalone report.

Supports enhanced data including:
- File type breakdown
- Old file analysis
- Duplicate detection results
- Trend data

Usage:
    build_report.py <analysis.json> [output.html]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import log, load_json

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "report_template_enhanced.html")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
        "~/Desktop/storage-report.html")

    data = load_json(src)
    if not data:
        log("Error: Could not load analysis file", "report")
        sys.exit(1)
    
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()

    blob = json.dumps(data, ensure_ascii=False)
    html = tpl.replace("__REPORT_DATA__", blob).replace("__DELETE_CONFIG__", "null")

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    
    log(f"Report generated: {out}", "report")
    
    # Print data summary
    extra = data.get("extra_data", {})
    if extra:
        if extra.get("duplicates"):
            log(f"  Duplicates: {extra['duplicates'].get('total_wasted_h', '?')} wasted", "report")
        if extra.get("file_types"):
            log(f"  File types: {extra['file_types'].get('total_files', '?')} files analyzed", "report")
        if extra.get("old_files"):
            log(f"  Old files: {extra['old_files'].get('summary', {}).get('total_h', '?')}", "report")


if __name__ == "__main__":
    main()
