#!/usr/bin/env python3
"""Standalone hybrid scanner - thin wrapper around engine scan functions.
Usage: python scan_hybrid.py [--deep]
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scan_all, scan_sys, disks, PP

def main():
    deep = "--deep" in sys.argv
    dd = disks()
    groups = scan_all(use_cache=False)
    si = scan_sys() if deep else []
    out = {"disks": dd, "groups": {k: len(v) for k,v in groups.items()},
           "items": sum((list(v) for v in groups.values()), []),
           "system_items": si}
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
