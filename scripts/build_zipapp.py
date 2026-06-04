"""Build a zipapp bundle, excluding tests / caches / prebuilt archives."""
import os
import shutil
import sys
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "zipapp-stage"
TARGET = ROOT / "storage-analyzer.pyz"

EXCLUDE_DIRS = {"tests", "__pycache__", ".pytest_cache", "build", ".git", "__pycache__"}
EXCLUDE_FILES = {".removed", ".pyz", ".pyc"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".removed", ".pyz"}


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    return False


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    include_count = 0
    for src in ROOT.iterdir():
        rel = src.relative_to(ROOT)
        if should_skip(rel):
            continue
        dest = STAGE / rel.name
        if src.is_dir():
            shutil.copytree(src, dest, ignore=lambda d, names: {
                n for n in names
                if should_skip(Path(d) / n)
            })
            include_count += sum(1 for _ in dest.rglob("*.py"))
        else:
            shutil.copy2(src, dest)
            if src.suffix == ".py":
                include_count += 1
    print(f"  staged {include_count} .py files")
    return STAGE


def main():
    print("Staging clean source tree...")
    stage()
    print(f"Building zipapp at {TARGET}...")
    zipapp.create_archive(str(STAGE), target=str(TARGET))
    size_kb = TARGET.stat().st_size / 1024
    print(f"  {TARGET.name}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
