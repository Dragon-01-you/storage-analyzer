"""Compare legacy scan_sys() vs new scan_sys_v2() output.

Catches regressions when switching the default scanner.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from engine.scanner import scan_sys
    from engine.scanner_v2 import scan_sys_v2

    legacy = scan_sys()
    modern = scan_sys_v2()

    print(f"Legacy scan_sys():     {len(legacy)} items")
    print(f"Modern scan_sys_v2():  {len(modern)} items")

    def names(items):
        return sorted({i.get("n") for i in items})

    legacy_names = set(names(legacy))
    modern_names = set(names(modern))

    print()
    print("=== In legacy but NOT in modern (missing) ===")
    for n in sorted(legacy_names - modern_names):
        print(f"  - {n}")

    print()
    print("=== In modern but NOT in legacy (new) ===")
    for n in sorted(modern_names - legacy_names):
        print(f"  + {n}")

    print()
    print(f"Common: {len(legacy_names & modern_names)}")
    print(f"Legacy-only: {len(legacy_names - modern_names)}")
    print(f"Modern-only: {len(modern_names - legacy_names)}")


if __name__ == "__main__":
    main()
