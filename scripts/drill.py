"""Drill into a directory to find which subdirs are eating space."""
import os
import sys
from pathlib import Path


def dir_size(p: Path) -> int:
    total = 0
    try:
        for root, _, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def drill(root: Path, depth: int = 2, top: int = 12):
    print(f"\n=== {root} (depth {depth}, top {top}) ===")
    items = []
    for r, dirs, files in os.walk(root):
        rel = os.path.relpath(r, root)
        depth_here = 0 if rel == "." else rel.count(os.sep)
        if depth_here >= depth:
            # Don't recurse further into the deepest level
            sz = sum((os.path.getsize(os.path.join(r, f)) for f in files if (lambda p: True)(os.path.join(r, f))), 0)
            items.append((sz, rel if rel != "." else "(root)"))
            # Mark dirs so we don't recurse
            dirs[:] = []
        else:
            # We are at intermediate level, let os.walk recurse naturally
            pass

    items.sort(reverse=True)
    for sz, rel in items[:top]:
        mb = sz / 1024 / 1024
        print(f"  {mb:10.1f} MB  {rel}")


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        r"C:\Users\ASUS\AppData\Local\Microsoft",
        r"C:\Users\ASUS\AppData\Local\wsl",
        r"C:\Users\ASUS\AppData\Roaming\Shandianshuo",
        r"C:\Users\ASUS\AppData\Roaming\TRAE SOLO CN",
        r"C:\Users\ASUS\AppData\Roaming\IDM",
    ]
    for t in targets:
        drill(Path(t), depth=2, top=10)
