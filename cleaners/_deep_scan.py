"""Deep scan cleaners: .bak, .DS_Store, node_modules, venv, __pycache__, Thumbs.db, temp files.

BleachBit's deepscan.xml covers these; we're adding parity.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Backup files (.bak, ~, .orig)
# ---------------------------------------------------------------------------

class BackupFilesCleaner(Cleaner):
    name = "backup-files"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Backup files (.bak, ~, .orig, .tmp)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = [ctx.home]
        if ctx.is_windows:
            scan_dirs.extend([
                os.path.join(ctx.home, "Documents"),
                os.path.join(ctx.home, "Desktop"),
            ])
        for scan_dir in scan_dirs:
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 3:
                        dirs.clear()
                        continue
                    for f in files:
                        if f.lower().endswith(('.bak', '.orig', '.tmp')) or f.endswith('~'):
                            fp = os.path.join(root, f)
                            try:
                                s = os.path.getsize(fp)
                                if s > 1024 * 1024:  # >1MB
                                    out.append(Entry(
                                        name=f"Backup: {f}",
                                        path=fp,
                                        size_kb=s // 1024, size_h=hk(s // 1024),
                                        reason="Backup/temp file (safe to delete if not needed)",
                                        risk="none", prio=3, cat="system", safe=True,
                                    ))
                            except OSError:
                                pass
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# .DS_Store (macOS)
# ---------------------------------------------------------------------------

class DSStoreCleaner(Cleaner):
    name = "ds-store"
    platforms = ("macos",)
    risk_level = "none"
    category = "system"
    description = ".DS_Store files (macOS Finder metadata)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_macos:
            return []
        out = []
        try:
            for root, dirs, files in os.walk(ctx.home):
                depth = root.replace(ctx.home, '').count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                for f in files:
                    if f == '.DS_Store':
                        fp = os.path.join(root, f)
                        try:
                            s = os.path.getsize(fp)
                            if s > 1024:  # >1KB
                                out.append(Entry(
                                    name=".DS_Store",
                                    path=fp,
                                    size_kb=s // 1024, size_h=hk(s // 1024),
                                    reason="macOS Finder metadata (auto-rebuilt)",
                                    risk="none", prio=4, cat="system", safe=True,
                                ))
                        except OSError:
                            pass
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Thumbs.db (Windows)
# ---------------------------------------------------------------------------

class ThumbsDbCleaner(Cleaner):
    name = "thumbs-db"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Thumbs.db files (Windows thumbnail cache)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        scan_dirs = [
            os.path.join(ctx.home, "Documents"),
            os.path.join(ctx.home, "Desktop"),
            os.path.join(ctx.home, "Pictures"),
            os.path.join(ctx.home, "Downloads"),
        ]
        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 3:
                        dirs.clear()
                        continue
                    for f in files:
                        if f.lower() in ('thumbs.db', 'thumbs.db:encryptable'):
                            fp = os.path.join(root, f)
                            try:
                                s = os.path.getsize(fp)
                                out.append(Entry(
                                    name="Thumbs.db",
                                    path=fp,
                                    size_kb=s // 1024, size_h=hk(s // 1024),
                                    reason="Windows thumbnail cache (auto-rebuilt)",
                                    risk="none", prio=4, cat="system", safe=True,
                                ))
                            except OSError:
                                pass
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# node_modules directories
# ---------------------------------------------------------------------------

class NodeModulesCleaner(Cleaner):
    name = "node-modules"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "node_modules directories (reinstall with npm install)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = [
            os.path.join(ctx.home, "Documents"),
            os.path.join(ctx.home, "Desktop"),
            os.path.join(ctx.home, "Projects"),
        ]
        if ctx.is_windows:
            scan_dirs.append(os.path.join(ctx.home, "source"))
        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 4:
                        dirs.clear()
                        continue
                    if 'node_modules' in dirs:
                        nm_path = os.path.join(root, 'node_modules')
                        s = _fast_szd(nm_path, 5)
                        if s > 100 * 1024 * 1024:  # >100MB
                            out.append(Entry(
                                name=f"node_modules: {os.path.basename(root)}",
                                path=nm_path,
                                size_kb=s // 1024, size_h=hk(s // 1024),
                                reason="node_modules (npm install to reinstall)",
                                risk="none", prio=3, cat="dev", safe=True,
                            ))
                        # Don't recurse into node_modules
                        dirs.remove('node_modules')
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# Python venv directories
# ---------------------------------------------------------------------------

class VenvCleaner(Cleaner):
    name = "python-venv"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Python virtual environments (venv, .venv)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = [
            os.path.join(ctx.home, "Documents"),
            os.path.join(ctx.home, "Desktop"),
            os.path.join(ctx.home, "Projects"),
        ]
        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 4:
                        dirs.clear()
                        continue
                    for d in list(dirs):
                        if d in ('venv', '.venv'):
                            venv_path = os.path.join(root, d)
                            # Check if it's actually a venv (has pyvenv.cfg)
                            if _exists(os.path.join(venv_path, 'pyvenv.cfg')):
                                s = _fast_szd(venv_path, 5)
                                if s > 50 * 1024 * 1024:  # >50MB
                                    out.append(Entry(
                                        name=f"venv: {os.path.basename(root)}",
                                        path=venv_path,
                                        size_kb=s // 1024, size_h=hk(s // 1024),
                                        reason="Python venv (python -m venv to recreate)",
                                        risk="none", prio=3, cat="dev", safe=True,
                                    ))
                            dirs.remove(d)
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# __pycache__ directories
# ---------------------------------------------------------------------------

class PycacheCleaner(Cleaner):
    name = "pycache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "__pycache__ directories (Python bytecode cache)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = [
            os.path.join(ctx.home, "Documents"),
            os.path.join(ctx.home, "Desktop"),
            os.path.join(ctx.home, "Projects"),
        ]
        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 5:
                        dirs.clear()
                        continue
                    if '__pycache__' in dirs:
                        cache_path = os.path.join(root, '__pycache__')
                        s = _fast_szd(cache_path, 5)
                        if s > 1024 * 1024:  # >1MB
                            out.append(Entry(
                                name=f"__pycache__: {os.path.basename(root)}",
                                path=cache_path,
                                size_kb=s // 1024, size_h=hk(s // 1024),
                                reason="Python bytecode cache (auto-rebuilt)",
                                risk="none", prio=4, cat="dev", safe=True,
                            ))
                        dirs.remove('__pycache__')
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# Old ISO/DMG/installer files
# ---------------------------------------------------------------------------

class OldInstallersCleaner(Cleaner):
    name = "old-installers"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Old installer files (.iso, .dmg, .msi, .exe in Downloads)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        downloads = os.path.join(ctx.home, "Downloads")
        if not _exists(downloads):
            return []
        try:
            for f in os.listdir(downloads):
                fl = f.lower()
                if fl.endswith(('.iso', '.dmg', '.msi', '.img', '.vhd', '.vhdx')):
                    fp = os.path.join(downloads, f)
                    try:
                        s = os.path.getsize(fp)
                        if s > 100 * 1024 * 1024:  # >100MB
                            out.append(Entry(
                                name=f"Installer: {f}",
                                path=fp,
                                size_kb=s // 1024, size_h=hk(s // 1024),
                                reason="Old installer/disk image in Downloads",
                                risk="none", prio=3, cat="system", safe=True,
                            ))
                    except OSError:
                        pass
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

DEEP_SCAN_CLEANERS = [
    BackupFilesCleaner,
    DSStoreCleaner,
    ThumbsDbCleaner,
    NodeModulesCleaner,
    VenvCleaner,
    PycacheCleaner,
    OldInstallersCleaner,
]
