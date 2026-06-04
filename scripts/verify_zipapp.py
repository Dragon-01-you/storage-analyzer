"""Verify the zipapp can run --deep and produce a parseable result."""
import json
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYZ = ROOT / "storage-analyzer.pyz"

if not PYZ.exists():
    print(f"NOT FOUND: {PYZ}")
    sys.exit(1)

print(f"Testing: {PYZ.name} ({PYZ.stat().st_size / 1024:.1f} KB)")
r = subprocess.run(
    [sys.executable, str(PYZ), "--deep", "--json"],
    capture_output=True, text=True, timeout=120,
)
# The zipapp prints JSON to stdout. Errors go to stderr.
if r.returncode != 0:
    print(f"EXIT {r.returncode}")
    print("STDERR:", r.stderr[-500:])
    sys.exit(1)

try:
    d = json.loads(r.stdout)
except json.JSONDecodeError as e:
    print("STDOUT (first 200):", r.stdout[:200])
    print("STDOUT (last 200):", r.stdout[-200:])
    raise

print(f"  ZIPAPP WORKS!  safe_h = {d['safe_h']}  actions = {len(d['actions'])}")
print(f"  drives: {list(d['disks'].keys())}")
print(f"  elapsed: {d['elapsed']}s")
