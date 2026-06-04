"""Show VM breakdown + drives after cleanup."""
import json
import subprocess
import sys


def main():
    r = subprocess.run(
        [sys.executable, "run.py", "--deep", "--json"],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(r.stdout)

    print("=== VM items (review tier) ===")
    for a in d["actions"]:
        if a.get("cat") == "vm":
            print(f"  {a['sz']:>10s}  [{a['act']}]  {a['what']}")

    print()
    print("=== Drives (after cleanup) ===")
    for k, v in d["disks"].items():
        bar = "#" * int(v["p"] / 5) + "-" * (20 - int(v["p"] / 5))
        print(f"  {k}: [{bar}] {v['p']}%  {v['uh']}/{v['th']}  free={v['fh']}")

    print()
    print(f"  safe_h = {d['safe_h']}")
    print(f"  elapsed = {d['elapsed']}s")


if __name__ == "__main__":
    main()
