#!/usr/bin/env python3
"""Standalone classifier - thin wrapper around engine._classify_item.
Usage: python classify.py <json_scan_file>
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import _classify_item

def main():
    if len(sys.argv) < 2:
        print("Usage: python classify.py <scan_output.json>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for a in data.get("actions", []):
        tier, reason, conf = _classify_item(
            a.get("what",""), a.get("path",""),
            a.get("cat","unknown"), 0)
        a["tier"] = tier; a["reason"] = reason; a["confidence"] = conf
        results.append(a)
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
