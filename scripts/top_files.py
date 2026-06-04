"""Even deeper drill - sort by file size at leaf."""
import os
import sys
from pathlib import Path


def top_files(root: Path, top: int = 15):
    print(f"\n=== Top {top} largest files in {root} ===")
    files = []
    for r, _, fs in os.walk(root):
        for f in fs:
            full = os.path.join(r, f)
            try:
                sz = os.path.getsize(full)
                files.append((sz, full))
            except OSError:
                pass
    files.sort(reverse=True)
    total = sum(s for s, _ in files)
    for sz, full in files[:top]:
        mb = sz / 1024 / 1024
        rel = os.path.relpath(full, root)
        print(f"  {mb:10.1f} MB  {rel}")
    print(f"  total scanned: {len(files)} files, {total/1024/1024:.1f} MB")


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        r"C:\Users\ASUS\AppData\Local\wsl",
        r"C:\Users\ASUS\AppData\Roaming\Shandianshuo",
        r"C:\Users\ASUS\AppData\Roaming\TRAE SOLO CN",
    ]
    for t in targets:
        top_files(Path(t), top=15)
