"""Unit tests for the cleaner plugin pipeline.

Strategy:
  1. Generic test: every registered cleaner can be instantiated and
     analyze() returns list[Entry] without crashing (on this platform).
  2. Per-cleaner depth tests: build a fake directory tree in tmp_path,
     point ScanContext at it, assert the cleaner surfaces the expected
     entry.
  3. VM test: spin up a fake .vmdk layout and check the VMwareCleaner
     parses the snapshot structure correctly.
"""
import os
import sys
import json
import platform
from pathlib import Path

# Allow running from project root
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import pytest

from cleaners import REGISTRY, run_all, ScanContext
from cleaners._base import Cleaner, Entry, ScanContext as SC
from cleaners import (
    _system, _browsers, _dev, _ide, _cloud_chat, _vmware,
)
from cleaners._vmware import _analyze_vm


# ---------------------------------------------------------------------------
# Generic smoke test for EVERY registered cleaner
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cleaner_cls", REGISTRY, ids=lambda c: c.__name__)
def test_cleaner_smoke(cleaner_cls):
    """Each cleaner must instantiate and have required metadata."""
    c = cleaner_cls()
    assert c.name, f"{cleaner_cls.__name__} missing name"
    assert c.platforms, f"{c.name} missing platforms"
    assert c.risk_level in ("none", "med", "high"), f"{c.name} bad risk"
    assert c.category, f"{c.name} missing category"
    # supported_on must accept the real context
    real_ctx = ScanContext.build()
    if c.supported_on(real_ctx):
        # Only attempt analyze on supported platforms
        entries = c.analyze(real_ctx)
        assert isinstance(entries, list)
        for e in entries:
            assert isinstance(e, Entry)
            assert e.name
            assert e.path


# ---------------------------------------------------------------------------
# Fake context helper
# ---------------------------------------------------------------------------

class FakePlatform:
    """Pretend to be any OS."""
    def __init__(self, which):
        self.which = which  # "windows" / "macos" / "linux"

    @property
    def is_windows(self): return self.which == "windows"
    @property
    def is_macos(self): return self.which == "macos"
    @property
    def is_linux(self): return self.which == "linux"


def make_ctx(home: Path, system_root: Path, which: str) -> ScanContext:
    """Build a ScanContext that points at a fake home directory."""
    fp = FakePlatform(which)
    pp = {}
    cfg = {"classify": {"green": [], "red": [], "known_apps": {}},
           "protected_paths": []}
    return ScanContext(
        home=str(home),
        system_root=str(system_root),
        is_windows=fp.is_windows,
        is_macos=fp.is_macos,
        is_linux=fp.is_linux,
        pp=pp,
        config=cfg,
        protected=set(),
    )


def touch(p: Path, size_mb: int = 1):
    """Create a file of approx size_mb MB."""
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\0" * (size_mb * 1024 * 1024))


# ---------------------------------------------------------------------------
# Per-platform coverage of representative cleaners
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("which", ["windows", "macos", "linux"])
def test_npm_cache_finds_cache(tmp_path, which):
    """NpmCacheCleaner must surface the platform-correct cache dir."""
    home = tmp_path / "home"
    home.mkdir()

    if which == "windows":
        cache = home / "AppData" / "Local" / "npm-cache"
    else:
        cache = home / ".npm" / "_cacache"
    touch(cache / "index", size_mb=120)

    ctx = make_ctx(home, home, which)
    from cleaners._dev import NpmCacheCleaner
    entries = NpmCacheCleaner().analyze(ctx)
    assert len(entries) == 1, f"expected 1 entry, got {len(entries)}: {entries}"
    assert "npm" in entries[0].name.lower()


@pytest.mark.parametrize("which", ["windows", "macos", "linux"])
def test_vscode_cache_finds_subdirs(tmp_path, which):
    """VSCodeCacheCleaner must surface subdirs (Cache, GPUCache, etc)."""
    home = tmp_path / "home"
    home.mkdir()
    if which == "windows":
        base = home / "AppData" / "Roaming" / "Code"
    elif which == "macos":
        base = home / "Library" / "Application Support" / "Code"
    else:
        base = home / ".config" / "Code"

    touch(base / "Cache" / "data_0", size_mb=200)

    ctx = make_ctx(home, home, which)
    from cleaners._ide import VSCodeCacheCleaner
    entries = VSCodeCacheCleaner().analyze(ctx)
    assert len(entries) >= 1
    assert any("Cache" in e.name for e in entries)


@pytest.mark.parametrize("which", ["windows", "macos", "linux"])
def test_chrome_cache_finds_default(tmp_path, which):
    """ChromeCacheCleaner must surface the Chrome Default/Cache dir."""
    home = tmp_path / "home"
    home.mkdir()
    if which == "windows":
        cache = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    elif which == "macos":
        cache = home / "Library" / "Caches" / "Google" / "Chrome" / "Default" / "Cache"
    else:
        cache = home / ".config" / "google-chrome" / "Default" / "Cache"
    touch(cache / "f_000001", size_mb=80)

    ctx = make_ctx(home, home, which)
    from cleaners._browsers import ChromeCacheCleaner
    entries = ChromeCacheCleaner().analyze(ctx)
    assert len(entries) == 1
    assert "Chrome" in entries[0].name


# ---------------------------------------------------------------------------
# VMwareCleaner: snapshot structure parsing
# ---------------------------------------------------------------------------

def _make_fake_vm(root: Path) -> None:
    """Build a fake VM with 1 base + 2 snapshot chains + .lck + .log."""
    root.mkdir(parents=True, exist_ok=True)

    def w(name: str, content: str = "x"):
        p = root / name
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    w("Debian12.vmx", "config")
    w("Debian12.nvram", "nvram")
    w("Debian12.vmsd", "vmsd")

    # Base disk
    touch(root / "Debian12.vmdk", size_mb=2)
    for i in range(1, 4):
        touch(root / f"Debian12-s00{i}.vmdk", size_mb=2)

    # Snapshot1
    touch(root / "Debian12-000001.vmdk", size_mb=1)
    for i in range(1, 4):
        touch(root / f"Debian12-000001-s00{i}.vmdk", size_mb=1)
    touch(root / "Debian12-Snapshot1.vmsn", size_mb=1)
    touch(root / "Debian12-Snapshot1.vmem", size_mb=64)

    # Snapshot2
    touch(root / "Debian12-000002.vmdk", size_mb=1)
    for i in range(1, 4):
        touch(root / f"Debian12-000002-s00{i}.vmdk", size_mb=1)
    touch(root / "Debian12-Snapshot2.vmsn", size_mb=1)

    # Lock + log
    (root / "Debian12.vmx.lck").mkdir()
    w("vmware-0.log", "x" * 1024)
    w("vmware.log", "x" * 1024)


def test_vmware_analyze_parses_snapshots(tmp_path):
    root = tmp_path / "vm"
    _make_fake_vm(root)

    report = _analyze_vm(str(root))
    # 1 base vmdk + 3 base splits + 2 snapshot deltas + 6 snapshot splits = 12
    assert report["vmdk_files"] == 12
    assert report["lck_count"] == 1
    assert report["log_bytes"] == 2048
    assert report["vmem_bytes"] >= 64 * 1024 * 1024
    # Should detect 2 snapshot layers (Debian12-000001, Debian12-000002)
    snap_layers = [s for s in report["snapshots"] if s["base"].endswith("-000001") or s["base"].endswith("-000002")]
    assert len(snap_layers) == 2, f"expected 2 snap layers, got {len(snap_layers)}: {[s['base'] for s in report['snapshots']]}"


def test_vmware_cleaner_advises_snapshot_merge(tmp_path):
    root = tmp_path / "vm"
    _make_fake_vm(root)
    home = tmp_path / "home"
    ctx = make_ctx(home, home, "windows")
    # Inject the fake VM path via the cleaner's default scan or via config
    from cleaners._vmware import VMwareCleaner
    c = VMwareCleaner()
    # Manually patch the default scan to point at our fake VM
    import cleaners._vmware as vmw
    orig = vmw._scan_default_paths
    vmw._scan_default_paths = lambda: [str(root)]
    try:
        entries = c.analyze(ctx)
    finally:
        vmw._scan_default_paths = orig
    assert len(entries) == 1
    e = entries[0]
    assert e.cat == "vm"
    assert e.risk == "med"
    # The extra blob carries the parsed report
    assert "vmware_report" in e.extra
    assert e.extra["snapshot_merge_bytes"] > 0


# ---------------------------------------------------------------------------
# Registry discipline
# ---------------------------------------------------------------------------

def test_registry_no_duplicate_names():
    names = [c.name for c in REGISTRY]
    assert len(names) == len(set(names)), f"duplicate cleaner names: {names}"


def test_registry_all_have_category():
    for c in REGISTRY:
        assert c.category, f"{c.__name__} missing category"
