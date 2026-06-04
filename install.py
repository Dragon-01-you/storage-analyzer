#!/usr/bin/env python3
"""One-line installer for Storage Analyzer.

Usage:
    python install.py          # pip install in current env
    python install.py --dev    # pip install -e . (developer mode)
    python install.py --check  # check if installed correctly
"""
import subprocess
import sys
import os

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print("Checking installation...")
        try:
            from v8 import Orchestrator, ScanConfig, ProtectedPaths
            print("  [OK] v8 core modules importable")
            from v8 import SafeDeleter, AuditLogger, DuplicateDetector
            print("  [OK] safeguard, audit, duplicates importable")
            pp = ProtectedPaths()
            assert pp.is_protected(r"C:\Windows\System32")
            print("  [OK] ProtectedPaths working")
            print("\nInstallation verified successfully!")
        except ImportError as e:
            print(f"  [FAIL] Import error: {e}")
            print("  Run: python install.py")
            sys.exit(1)
        return

    dev_mode = len(sys.argv) > 1 and sys.argv[1] == "--dev"

    print("Storage Analyzer v8.1.0 Installer")
    print("=" * 40)

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10+ required, you have {sys.version}")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}")

    # Install
    if dev_mode:
        print("\nInstalling in developer mode (editable)...")
        cmd = [sys.executable, "-m", "pip", "install", "-e", ".[full,dev]"]
    else:
        print("\nInstalling...")
        cmd = [sys.executable, "-m", "pip", "install", "."]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[OK] Installed successfully!")
    else:
        print(f"[ERROR] Installation failed:\n{result.stderr}")
        sys.exit(1)

    # Verify
    print("\nVerifying...")
    result = subprocess.run(
        [sys.executable, "-c", "from v8 import Orchestrator; print('OK')"],
        capture_output=True, text=True
    )
    if "OK" in result.stdout:
        print("[OK] v8 modules importable")
    else:
        print(f"[WARN] Import check failed: {result.stderr}")

    print("\nDone! Usage:")
    print("  python run.py --deep --json -o scan.json   # Scan")
    print("  python run.py --deep --execute             # Clean")
    print("  python -m pytest tests/test_v8.py -v       # Test")

if __name__ == "__main__":
    main()
