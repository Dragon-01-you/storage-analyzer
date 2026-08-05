"""Office and mail client cleaners: Microsoft Office, LibreOffice, Thunderbird.

BleachBit covers these; we're adding parity.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Microsoft Office
# ---------------------------------------------------------------------------

class OfficeCacheCleaner(Cleaner):
    name = "office-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "office"
    description = "Microsoft Office cache and temp files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Office temp files
        office_temp = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "Office")
        if _exists(office_temp) and os.path.isdir(office_temp):
            # Only cache subdirs
            for subdir in ["OTeleCache", "16.0", "15.0"]:
                cache_path = os.path.join(office_temp, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(Entry(
                            name=f"Office {subdir} Cache", path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Office cache (auto-rebuilt)",
                            risk="none", prio=2, cat="office", safe=True,
                        ))
        # Office recent files
        office_recent = os.path.join(ctx.home, "AppData", "Roaming", "Microsoft", "Office")
        if _exists(office_recent) and os.path.isdir(office_recent):
            s = _fast_szd(office_recent, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="Office Recent", path=office_recent,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Office recent files list (safe to clear)",
                    risk="none", prio=3, cat="office", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# LibreOffice
# ---------------------------------------------------------------------------

class LibreOfficeCacheCleaner(Cleaner):
    name = "libreoffice-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "office"
    description = "LibreOffice cache and backup files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "libreoffice")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "libreoffice")
        else:
            base = os.path.join(ctx.home, ".config", "libreoffice")
        if not _exists(base) or not os.path.isdir(base):
            return []
        # Cache
        cache = os.path.join(base, "cache")
        if _exists(cache) and os.path.isdir(cache):
            s = _fast_szd(cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="LibreOffice Cache", path=cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="LibreOffice cache (auto-rebuilt)",
                    risk="none", prio=2, cat="office", safe=True,
                ))
        # Backup
        backup = os.path.join(base, "user", "backup")
        if _exists(backup) and os.path.isdir(backup):
            s = _fast_szd(backup, 10)
            if s > 100 * 1024 * 1024:
                out.append(Entry(
                    name="LibreOffice Backup", path=backup,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="LibreOffice backup files (review before deleting)",
                    risk="med", prio=3, cat="office", safe=False,
                ))
        return out


# ---------------------------------------------------------------------------
# Thunderbird
# ---------------------------------------------------------------------------

class ThunderbirdCacheCleaner(Cleaner):
    name = "thunderbird-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "mail"
    description = "Thunderbird email client cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "Thunderbird", "Profiles")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "Thunderbird")
        else:
            base = os.path.join(ctx.home, ".cache", "thunderbird")
        if not _exists(base) or not os.path.isdir(base):
            return []
        try:
            for prof in os.listdir(base):
                cache_p = os.path.join(base, prof, "cache2")
                if os.path.isdir(cache_p):
                    s = _fast_szd(cache_p, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(Entry(
                            name="Thunderbird Cache", path=cache_p,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Thunderbird cache (auto-rebuilt)",
                            risk="none", prio=2, cat="mail", safe=True,
                        ))
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Outlook
# ---------------------------------------------------------------------------

class OutlookCacheCleaner(Cleaner):
    name = "outlook-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "mail"
    description = "Microsoft Outlook cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Outlook temp files
        outlook_temp = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "Outlook")
        if _exists(outlook_temp) and os.path.isdir(outlook_temp):
            for subdir in ["RoamCache", "Temp"]:
                cache_path = os.path.join(outlook_temp, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(Entry(
                            name="Outlook Cache", path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Outlook cache (auto-rebuilt)",
                            risk="none", prio=2, cat="mail", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

OFFICE_CLEANERS = [
    OfficeCacheCleaner,
    LibreOfficeCacheCleaner,
    ThunderbirdCacheCleaner,
    OutlookCacheCleaner,
]
