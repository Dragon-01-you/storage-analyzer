"""One-shot analyzer: deep scan + categorized summary."""
import json
import subprocess
import sys


def to_bytes(s: str) -> int:
    for m, u in [(1024 ** 3, "GB"), (1024 ** 2, "MB"), (1024 ** 1, "KB"), (1, "B")]:
        if u in s:
            try:
                return float(s.replace(u, "")) * m
            except ValueError:
                pass
    return 0


def main():
    r = subprocess.run(
        [sys.executable, "run.py", "--deep", "--json"],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(r.stdout)

    print("=" * 60)
    print("=== TOTAL ===")
    print("=" * 60)
    print(f"  Safe to reclaim (auto-clean green items): {d['safe_h']}")
    print(f"  Total actions surfaced:                  {len(d['actions'])}")
    print()

    print("=== DRIVES ===")
    for k, v in d["disks"].items():
        bar = "#" * int(v["p"] / 5) + "-" * (20 - int(v["p"] / 5))
        print(f"  {k}: [{bar}] {v['p']}%  {v['uh']}/{v['th']}  free={v['fh']}")
    print()

    print("=== TOP 15 CLEANABLE ===")
    for a in d["actions"][:15]:
        print(f"  [{a['act']:6s}] {a['sz']:>10s}  [{a['risk']:>5s}] {a['what'][:70]}")
    print()

    print("=== BY CATEGORY (count + total size) ===")
    cats = {}
    for a in d["actions"]:
        c = a.get("cat", "?")
        if c not in cats:
            cats[c] = [0, 0]
        cats[c][0] += 1
        cats[c][1] += to_bytes(a["sz"])
    for c, (n, sz) in sorted(cats.items(), key=lambda x: -x[1][1]):
        print(f"  {c:10s} {n:3d} items   {sz / 1024 / 1024 / 1024:6.2f} GB")
    print()

    green = sum(1 for a in d["actions"] if a["act"] == "delete")
    review = sum(1 for a in d["actions"] if a["act"] == "review")
    keep = sum(1 for a in d["actions"] if a["act"] == "keep")
    print("=== ACT SPLIT ===")
    print(f"  delete  (auto-safe, --execute will clean): {green}")
    print(f"  review  (you should look at these):         {review}")
    print(f"  keep    (already protected / red tier):     {keep}")
    print()

    print("=== WARNINGS ===")
    for w in d.get("warnings", []):
        print(f"  [{w['lvl']}] {w['msg']}")


if __name__ == "__main__":
    main()
