"""Extra browser cleaners: Opera, Vivaldi, Chromium, Librewolf, Waterfox, Arc.

BleachBit covers these; we're adding parity.
Each targets cache ONLY — never bookmarks, passwords, or history.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


def _browser_cache_entry(bname: str, cache_path: str) -> Entry:
    s = _fast_szd(cache_path, 10)
    kb = s // 1024
    return Entry(
        name=f"{bname} Cache",
        path=cache_path,
        size_kb=kb,
        size_h=hk(kb),
        reason=f"{bname} browser cache (auto-rebuilt)",
        risk="none",
        prio=2,
        cat="browser",
        safe=True,
    )


# ---------------------------------------------------------------------------
# Opera
# ---------------------------------------------------------------------------

class OperaCacheCleaner(Cleaner):
    name = "opera-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "browser"
    description = "Opera browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            candidates = [
                os.path.join(ctx.home, "AppData", "Local", "Opera Software", "Opera Stable", "Cache"),
                os.path.join(ctx.home, "AppData", "Local", "Opera Software", "Opera GX Stable", "Cache"),
            ]
        elif ctx.is_macos:
            candidates = [
                os.path.join(ctx.home, "Library", "Caches", "com.operasoftware.Opera"),
            ]
        else:
            candidates = [
                os.path.join(ctx.home, ".config", "opera", "Cache"),
                os.path.join(ctx.home, ".config", "opera-gx", "Cache"),
            ]
        for c in candidates:
            if _exists(c) and os.path.isdir(c):
                s = _fast_szd(c, 10)
                if s > 50 * 1024 * 1024:
                    out.append(_browser_cache_entry("Opera", c))
        return out


# ---------------------------------------------------------------------------
# Vivaldi
# ---------------------------------------------------------------------------

class VivaldiCacheCleaner(Cleaner):
    name = "vivaldi-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "browser"
    description = "Vivaldi browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            candidates = [
                os.path.join(ctx.home, "AppData", "Local", "Vivaldi", "User Data", "Default", "Cache"),
            ]
        elif ctx.is_macos:
            candidates = [
                os.path.join(ctx.home, "Library", "Caches", "Vivaldi"),
            ]
        else:
            candidates = [
                os.path.join(ctx.home, ".config", "vivaldi", "Default", "Cache"),
            ]
        for c in candidates:
            if _exists(c) and os.path.isdir(c):
                s = _fast_szd(c, 10)
                if s > 50 * 1024 * 1024:
                    out.append(_browser_cache_entry("Vivaldi", c))
        return out


# ---------------------------------------------------------------------------
# Chromium
# ---------------------------------------------------------------------------

class ChromiumCacheCleaner(Cleaner):
    name = "chromium-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "browser"
    description = "Chromium browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            candidates = [
                os.path.join(ctx.home, "AppData", "Local", "Chromium", "User Data", "Default", "Cache"),
            ]
        elif ctx.is_macos:
            candidates = [
                os.path.join(ctx.home, "Library", "Caches", "Chromium"),
            ]
        else:
            candidates = [
                os.path.join(ctx.home, ".config", "chromium", "Default", "Cache"),
                os.path.join(ctx.home, "snap", "chromium", "common", "chromium", "Default", "Cache"),
            ]
        for c in candidates:
            if _exists(c) and os.path.isdir(c):
                s = _fast_szd(c, 10)
                if s > 50 * 1024 * 1024:
                    out.append(_browser_cache_entry("Chromium", c))
        return out


# ---------------------------------------------------------------------------
# LibreWolf
# ---------------------------------------------------------------------------

class LibreWolfCacheCleaner(Cleaner):
    name = "librewolf-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "browser"
    description = "LibreWolf browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "LibreWolf", "Profiles")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "LibreWolf")
        else:
            base = os.path.join(ctx.home, ".cache", "librewolf")
        if not _exists(base) or not os.path.isdir(base):
            return []
        try:
            for prof in os.listdir(base):
                cache_p = os.path.join(base, prof, "cache2")
                if os.path.isdir(cache_p):
                    s = _fast_szd(cache_p, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(_browser_cache_entry("LibreWolf", cache_p))
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Waterfox
# ---------------------------------------------------------------------------

class WaterfoxCacheCleaner(Cleaner):
    name = "waterfox-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "browser"
    description = "Waterfox browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "Waterfox", "Profiles")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "Waterfox")
        else:
            base = os.path.join(ctx.home, ".cache", "waterfox")
        if not _exists(base) or not os.path.isdir(base):
            return []
        try:
            for prof in os.listdir(base):
                cache_p = os.path.join(base, prof, "cache2")
                if os.path.isdir(cache_p):
                    s = _fast_szd(cache_p, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(_browser_cache_entry("Waterfox", cache_p))
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# Arc Browser
# ---------------------------------------------------------------------------

class ArcCacheCleaner(Cleaner):
    name = "arc-cache"
    platforms = ("windows", "macos")
    risk_level = "none"
    category = "browser"
    description = "Arc browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            candidates = [
                os.path.join(ctx.home, "AppData", "Local", "Arc", "User Data", "Default", "Cache"),
            ]
        elif ctx.is_macos:
            candidates = [
                os.path.join(ctx.home, "Library", "Caches", "company.thebrowser.Browser"),
            ]
        else:
            return []
        for c in candidates:
            if _exists(c) and os.path.isdir(c):
                s = _fast_szd(c, 10)
                if s > 50 * 1024 * 1024:
                    out.append(_browser_cache_entry("Arc", c))
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

BROWSER_CLEANERS_EXTRA_NEW = [
    OperaCacheCleaner,
    VivaldiCacheCleaner,
    ChromiumCacheCleaner,
    LibreWolfCacheCleaner,
    WaterfoxCacheCleaner,
    ArcCacheCleaner,
]
