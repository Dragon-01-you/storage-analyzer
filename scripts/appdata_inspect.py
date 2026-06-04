"""Find the largest subdirectories in AppData."""
import os
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))


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


def scan(label: str, root: Path, threshold_mb: int = 100):
    print(f"\n=== {label} ({root}) - > {threshold_mb}MB ===")
    items = []
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            sz = dir_size(child)
            mb = sz / 1024 / 1024
            if mb >= threshold_mb:
                items.append((mb, child.name))
    except OSError as e:
        print(f"  ERR: {e}")
        return
    items.sort(reverse=True)
    for mb, name in items[:25]:
        print(f"  {mb:10.1f} MB  {name}")


if __name__ == "__main__":
    scan("LOCAL", HOME / "AppData" / "Local")
    scan("ROAMING", HOME / "AppData" / "Roaming")
    scan("LOCALLOW", HOME / "AppData" / "LocalLow")
