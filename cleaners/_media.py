"""Media and utility app cleaners: VLC, Spotify, Adobe Reader, WinRAR, 7-Zip.

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
# VLC
# ---------------------------------------------------------------------------

class VLCCacheCleaner(Cleaner):
    name = "vlc-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "media"
    description = "VLC media player cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            cache = os.path.join(ctx.home, "AppData", "Local", "VLC")
        elif ctx.is_macos:
            cache = os.path.join(ctx.home, "Library", "Caches", "org.videolan.vlc")
        else:
            cache = os.path.join(ctx.home, ".cache", "vlc")
        if _exists(cache) and os.path.isdir(cache):
            s = _fast_szd(cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="VLC Cache", path=cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="VLC cache (auto-rebuilt)",
                    risk="none", prio=2, cat="media", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Spotify
# ---------------------------------------------------------------------------

class SpotifyCacheCleaner(Cleaner):
    name = "spotify-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "media"
    description = "Spotify cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            cache = os.path.join(ctx.home, "AppData", "Local", "Spotify", "Storage")
        elif ctx.is_macos:
            cache = os.path.join(ctx.home, "Library", "Caches", "com.spotify.client")
        else:
            cache = os.path.join(ctx.home, ".cache", "spotify")
        if _exists(cache) and os.path.isdir(cache):
            s = _fast_szd(cache, 10)
            if s > 500 * 1024 * 1024:  # >500MB
                out.append(Entry(
                    name="Spotify Cache", path=cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Spotify cache (auto-rebuilt, re-downloads songs)",
                    risk="none", prio=2, cat="media", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Adobe Reader
# ---------------------------------------------------------------------------

class AdobeReaderCacheCleaner(Cleaner):
    name = "adobe-reader-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "office"
    description = "Adobe Reader cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        cache = os.path.join(ctx.home, "AppData", "Local", "Adobe", "Acrobat")
        if _exists(cache) and os.path.isdir(cache):
            for subdir in ["Cache", "DC", "2020"]:
                cache_path = os.path.join(cache, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(Entry(
                            name="Adobe Reader Cache", path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Adobe Reader cache (auto-rebuilt)",
                            risk="none", prio=2, cat="office", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# WinRAR
# ---------------------------------------------------------------------------

class WinRARCacheCleaner(Cleaner):
    name = "winrar-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "WinRAR temp and recent files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # WinRAR temp
        temp = os.path.join(ctx.home, "AppData", "Roaming", "WinRAR")
        if _exists(temp) and os.path.isdir(temp):
            s = _fast_szd(temp, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="WinRAR Temp", path=temp,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="WinRAR temp files (safe to clear)",
                    risk="none", prio=3, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# 7-Zip
# ---------------------------------------------------------------------------

class SevenZipCacheCleaner(Cleaner):
    name = "7zip-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "7-Zip temp files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        temp = os.path.join(ctx.home, "AppData", "Local", "7-Zip")
        if _exists(temp) and os.path.isdir(temp):
            s = _fast_szd(temp, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="7-Zip Temp", path=temp,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="7-Zip temp files (safe to clear)",
                    risk="none", prio=3, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Everything (search tool)
# ---------------------------------------------------------------------------

class EverythingCacheCleaner(Cleaner):
    name = "everything-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Everything search tool database"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        db = os.path.join(ctx.home, "AppData", "Local", "Everything", "Everything.db")
        if not _exists(db):
            return []
        try:
            s = os.path.getsize(db)
            if s > 100 * 1024 * 1024:  # >100MB
                return [Entry(
                    name="Everything DB", path=db,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Everything search index (auto-rebuilt on next launch)",
                    risk="none", prio=3, cat="system", safe=True,
                )]
        except OSError:
            pass
        return []


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

MEDIA_CLEANERS = [
    VLCCacheCleaner,
    SpotifyCacheCleaner,
    AdobeReaderCacheCleaner,
    WinRARCacheCleaner,
    SevenZipCacheCleaner,
    EverythingCacheCleaner,
]
