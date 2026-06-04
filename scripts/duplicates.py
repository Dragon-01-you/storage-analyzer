#!/usr/bin/env python3
"""Standalone duplicate finder - thin wrapper around engine.find_dupes.
Usage: python duplicates.py [--min-size 50]
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import find_dupes

def main():
    min_mb = 50
    for i, a in enumerate(sys.argv):
        if a == "--min-size" and i+1 < len(sys.argv):
            min_mb = int(sys.argv[i+1])
    dupes = find_dupes(min_mb)
    print(json.dumps(dupes, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
