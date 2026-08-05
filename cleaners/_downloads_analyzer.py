"""Downloads folder analyzer: smart detection of old, duplicate, and unnecessary files.

This is a unique feature not in BleachBit — smart analysis of Downloads folder.
"""
from __future__ import annotations
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


class DownloadsAnalyzer(Cleaner):
    name = "downloads-analyzer"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "Smart Downloads folder analysis (old files, duplicates, installers)"

    # File categories
    INSTALLER_EXTS = {'.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.appimage', '.snap', '.flatpak'}
    ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.tar.gz'}
    MEDIA_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.mp3', '.wav', '.flac', '.aac'}
    DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico'}

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        downloads = os.path.join(ctx.home, "Downloads")
        if not _exists(downloads) or not os.path.isdir(downloads):
            return []

        now = time.time()
        thirty_days_ago = now - (30 * 24 * 3600)
        ninety_days_ago = now - (90 * 24 * 3600)

        # Track file sizes by name for duplicate detection
        size_groups: Dict[int, List[str]] = defaultdict(list)
        total_size = 0
        old_files_size = 0
        installer_size = 0
        duplicate_size = 0
        old_files = []
        installers = []
        large_files = []

        try:
            for f in os.listdir(downloads):
                fp = os.path.join(downloads, f)
                if not os.path.isfile(fp):
                    continue
                try:
                    st = os.stat(fp)
                    size = st.st_size
                    mtime = st.st_mtime
                    ext = os.path.splitext(f)[1].lower()

                    total_size += size

                    # Track for duplicates
                    size_groups[size].append(fp)

                    # Old files (>90 days)
                    if mtime < ninety_days_ago and size > 10 * 1024 * 1024:  # >10MB
                        old_files.append((fp, f, size, mtime))
                        old_files_size += size

                    # Installers
                    if ext in self.INSTALLER_EXTS and size > 50 * 1024 * 1024:  # >50MB
                        installers.append((fp, f, size, mtime))
                        installer_size += size

                    # Large files (>500MB)
                    if size > 500 * 1024 * 1024:
                        large_files.append((fp, f, size, mtime))

                except OSError:
                    pass
        except OSError:
            return []

        # Find duplicates (same size files)
        for size, paths in size_groups.items():
            if len(paths) > 1 and size > 50 * 1024 * 1024:  # >50MB
                duplicate_size += size * (len(paths) - 1)

        # Generate entries
        if old_files_size > 500 * 1024 * 1024:  # >500MB
            out.append(Entry(
                name="Downloads: Old Files (>90 days)",
                path=downloads,
                size_kb=old_files_size // 1024,
                size_h=hk(old_files_size // 1024),
                reason=f"{len(old_files)} files older than 90 days in Downloads",
                risk="none", prio=3, cat="system", safe=True,
                extra={"type": "old_files", "files": old_files[:10]}  # Show first 10
            ))

        if installer_size > 500 * 1024 * 1024:  # >500MB
            out.append(Entry(
                name="Downloads: Installers",
                path=downloads,
                size_kb=installer_size // 1024,
                size_h=hk(installer_size // 1024),
                reason=f"{len(installers)} installer files in Downloads",
                risk="none", prio=3, cat="system", safe=True,
                extra={"type": "installers", "files": installers[:10]}
            ))

        if duplicate_size > 500 * 1024 * 1024:  # >500MB
            out.append(Entry(
                name="Downloads: Potential Duplicates",
                path=downloads,
                size_kb=duplicate_size // 1024,
                size_h=hk(duplicate_size // 1024),
                reason=f"Potential duplicate files (same size) in Downloads",
                risk="none", prio=3, cat="system", safe=True,
                extra={"type": "duplicates"}
            ))

        if large_files:
            large_size = sum(size for _, _, size, _ in large_files)
            if large_size > 1024 * 1024 * 1024:  # >1GB
                out.append(Entry(
                    name="Downloads: Large Files (>500MB)",
                    path=downloads,
                    size_kb=large_size // 1024,
                    size_h=hk(large_size // 1024),
                    reason=f"{len(large_files)} files larger than 500MB in Downloads",
                    risk="none", prio=3, cat="system", safe=True,
                    extra={"type": "large_files", "files": large_files[:10]}
                ))

        return out


# ---------------------------------------------------------------------------
# Temp files analyzer
# ---------------------------------------------------------------------------

class TempFilesCleaner(Cleaner):
    name = "temp-files"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "system"
    description = "System temporary files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            temp_dirs = [
                os.environ.get("TEMP", os.path.join(ctx.home, "AppData", "Local", "Temp")),
                os.path.join(ctx.system_root, "Temp"),
            ]
        elif ctx.is_macos:
            temp_dirs = ["/tmp", "/var/tmp"]
        else:
            temp_dirs = ["/tmp", "/var/tmp"]

        for temp_dir in temp_dirs:
            if not _exists(temp_dir) or not os.path.isdir(temp_dir):
                continue
            s = _fast_szd(temp_dir, 5)
            if s > 500 * 1024 * 1024:  # >500MB
                out.append(Entry(
                    name=f"Temp: {os.path.basename(temp_dir)}",
                    path=temp_dir,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="System temporary files (safe to clear)",
                    risk="none", prio=2, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Recycle Bin
# ---------------------------------------------------------------------------

class RecycleBinCleaner(Cleaner):
    name = "recycle-bin"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows Recycle Bin"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        # Recycle bin is at C:\$Recycle.Bin
        recycle_path = "C:\\$Recycle.Bin"
        if not _exists(recycle_path):
            return []
        try:
            total_size = 0
            for sid in os.listdir(recycle_path):
                sid_path = os.path.join(recycle_path, sid)
                if os.path.isdir(sid_path):
                    total_size += _fast_szd(sid_path, 5)
            if total_size < 100 * 1024 * 1024:  # <100MB
                return []
            return [Entry(
                name="Recycle Bin",
                path=recycle_path,
                size_kb=total_size // 1024,
                size_h=hk(total_size // 1024),
                reason="Windows Recycle Bin (permanently delete)",
                risk="none", prio=2, cat="system", safe=True,
            )]
        except OSError:
            return []


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

DOWNLOADS_CLEANERS = [
    DownloadsAnalyzer,
    TempFilesCleaner,
    RecycleBinCleaner,
]
