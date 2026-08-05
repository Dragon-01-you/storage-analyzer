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
# Log files cleaner
# ---------------------------------------------------------------------------

class LogFilesCleaner(Cleaner):
    name = "log-files"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Large log files (.log, .log.old, etc.)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = []
        if ctx.is_windows:
            scan_dirs = [
                os.path.join(ctx.home, "AppData", "Local"),
                os.path.join(ctx.home, "AppData", "Roaming"),
            ]
        else:
            scan_dirs = ["/var/log", os.path.join(ctx.home, ".local", "share")]

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
                        fl = f.lower()
                        if fl.endswith(('.log', '.log.old', '.log.1', '.log.2', '.log.3')):
                            fp = os.path.join(root, f)
                            try:
                                s = os.path.getsize(fp)
                                if s > 10 * 1024 * 1024:  # >10MB
                                    out.append(Entry(
                                        name=f"Log: {f}",
                                        path=fp,
                                        size_kb=s // 1024, size_h=hk(s // 1024),
                                        reason="Large log file (safe to delete)",
                                        risk="none", prio=3, cat="system", safe=True,
                                    ))
                            except OSError:
                                pass
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# Old downloads cleaner (>180 days)
# ---------------------------------------------------------------------------

class OldDownloadsCleaner(Cleaner):
    name = "old-downloads"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Files in Downloads older than 180 days"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        import time
        out = []
        downloads = os.path.join(ctx.home, "Downloads")
        if not _exists(downloads):
            return []

        now = time.time()
        threshold = now - (180 * 24 * 3600)  # 180 days

        try:
            for f in os.listdir(downloads):
                fp = os.path.join(downloads, f)
                if not os.path.isfile(fp):
                    continue
                try:
                    st = os.stat(fp)
                    if st.st_mtime < threshold and st.st_size > 50 * 1024 * 1024:  # >50MB
                        out.append(Entry(
                            name=f"Old: {f}",
                            path=fp,
                            size_kb=st.st_size // 1024,
                            size_h=hk(st.st_size // 1024),
                            reason=f"File older than 180 days in Downloads",
                            risk="none", prio=3, cat="system", safe=True,
                        ))
                except OSError:
                    pass
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Windows Update cleanup
# ---------------------------------------------------------------------------

class WindowsUpdateCleanup(Cleaner):
    name = "windows-update-cleanup"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows Update downloaded files"
    requires_privilege = True

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # SoftwareDistribution/Download
        wu_download = os.path.join(ctx.system_root, "SoftwareDistribution", "Download")
        if _exists(wu_download) and os.path.isdir(wu_download):
            s = _fast_szd(wu_download, 5)
            if s > 500 * 1024 * 1024:  # >500MB
                out.append(Entry(
                    name="Windows Update Downloads",
                    path=wu_download,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Windows Update downloaded files (safe after install)",
                    risk="none", prio=2, cat="system", safe=True,
                    needs_privilege=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Installer residuals
# ---------------------------------------------------------------------------

class InstallerResidualsCleaner(Cleaner):
    name = "installer-residuals"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Leftover installer files (setup_*.exe, install_*.exe)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        scan_dirs = [
            os.path.join(ctx.home, "Downloads"),
            os.path.join(ctx.home, "Desktop"),
            ctx.home,
        ]
        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for f in os.listdir(scan_dir):
                    fl = f.lower()
                    if (fl.startswith('setup_') or fl.startswith('install_') or
                            fl.startswith('installer_') or fl.endswith('_setup.exe') or
                            fl.endswith('_installer.exe')):
                        fp = os.path.join(scan_dir, f)
                        if os.path.isfile(fp):
                            try:
                                s = os.path.getsize(fp)
                                if s > 50 * 1024 * 1024:  # >50MB
                                    out.append(Entry(
                                        name=f"Installer: {f}",
                                        path=fp,
                                        size_kb=s // 1024, size_h=hk(s // 1024),
                                        reason="Leftover installer file",
                                        risk="none", prio=3, cat="system", safe=True,
                                    ))
                            except OSError:
                                pass
            except OSError:
                pass
        return out


# ---------------------------------------------------------------------------
# Crash dump files
# ---------------------------------------------------------------------------

class CrashDumpCleaner(Cleaner):
    name = "crash-dumps-deep"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Crash dump files (.dmp, .core, .crash)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        scan_dirs = [ctx.home]
        if ctx.is_windows:
            scan_dirs.extend([
                os.path.join(ctx.home, "AppData", "Local", "CrashDumps"),
                os.path.join(ctx.system_root, "Minidump"),
            ])
        else:
            scan_dirs.extend(["/var/crash", "/tmp"])

        for scan_dir in scan_dirs:
            if not _exists(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    depth = root.replace(scan_dir, '').count(os.sep)
                    if depth > 2:
                        dirs.clear()
                        continue
                    for f in files:
                        fl = f.lower()
                        if fl.endswith(('.dmp', '.core', '.crash', '.mdmp', '.hdmp')):
                            fp = os.path.join(root, f)
                            try:
                                s = os.path.getsize(fp)
                                if s > 10 * 1024 * 1024:  # >10MB
                                    out.append(Entry(
                                        name=f"Crash dump: {f}",
                                        path=fp,
                                        size_kb=s // 1024, size_h=hk(s // 1024),
                                        reason="Crash dump file (safe to delete)",
                                        risk="none", prio=2, cat="system", safe=True,
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
    LogFilesCleaner,
    OldDownloadsCleaner,
    WindowsUpdateCleanup,
    InstallerResidualsCleaner,
    CrashDumpCleaner,
]
