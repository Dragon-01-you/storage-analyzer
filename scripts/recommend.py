#!/usr/bin/env python3
"""Standalone recommender - thin wrapper around engine.gen_actions.
Usage: python recommend.py <scan_output.json>
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import gen_actions

def main():
    if len(sys.argv) < 2:
        print("Usage: python recommend.py <scan_output.json>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    groups = {}
    for item in data.get("items", []):
        cat = item.get("cat", "unknown")
        groups.setdefault(cat, []).append(item)
    actions = gen_actions(groups, data.get("system_items", []), dry_run=True)
    print(json.dumps(actions, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
