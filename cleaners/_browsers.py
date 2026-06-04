"""Browser cache cleaners: Chrome / Edge / Firefox / Brave / Opera.

Each cleaner targets the *cache subdirectory* of one browser's
default profile, not the entire profile (so bookmarks, history,
passwords, and extensions are preserved).
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, hk


def _browser_cache_entry(bname: str, cache_path: str) -> Entry:
    s = szd(cache_path, 3, 10)
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


class ChromeCacheCleaner(Cleaner):
    name = "chrome-cache"
    platforms = ("windows", "macos", "linux")
    description = "Google Chrome browser cache (Default profile)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        candidates = []
        if ctx.is_windows:
            candidates.append(os.path.join(ctx.home, "AppData", "Local",
                                            "Google", "Chrome", "User Data",
                                            "Default", "Cache"))
        elif ctx.is_macos:
            candidates.append(os.path.join(ctx.home, "Library", "Caches",
                                            "Google", "Chrome", "Default", "Cache"))
        elif ctx.is_linux:
            candidates.append(os.path.join(ctx.home, ".config", "google-chrome",
                                            "Default", "Cache"))
        out = []
        for c in candidates:
            if os.path.isdir(c) and szd(c, 1, 5) > 50 * 1024 * 1024:
                out.append(_browser_cache_entry("Chrome", c))
        return out


class EdgeCacheCleaner(Cleaner):
    name = "edge-cache"
    platforms = ("windows", "macos", "linux")
    description = "Microsoft Edge browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        candidates = []
        if ctx.is_windows:
            candidates.append(os.path.join(ctx.home, "AppData", "Local",
                                            "Microsoft", "Edge", "User Data",
                                            "Default", "Cache"))
        elif ctx.is_macos:
            candidates.append(os.path.join(ctx.home, "Library", "Caches",
                                            "Microsoft Edge", "Default", "Cache"))
        elif ctx.is_linux:
            candidates.append(os.path.join(ctx.home, ".config", "microsoft-edge",
                                            "Default", "Cache"))
        out = []
        for c in candidates:
            if os.path.isdir(c) and szd(c, 1, 5) > 50 * 1024 * 1024:
                out.append(_browser_cache_entry("Edge", c))
        return out


class FirefoxCacheCleaner(Cleaner):
    name = "firefox-cache"
    platforms = ("windows", "macos", "linux")
    description = "Mozilla Firefox cache (all profiles)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "Mozilla",
                                 "Firefox", "Profiles")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "Mozilla",
                                 "Firefox", "Profiles")
        elif ctx.is_linux:
            base = os.path.join(ctx.home, ".cache", "mozilla", "firefox")
        else:
            return []
        if not os.path.isdir(base):
            return []
        out = []
        try:
            for prof in os.listdir(base):
                cache_p = os.path.join(base, prof, "cache2")
                if os.path.isdir(cache_p):
                    s = szd(cache_p, 1, 5)
                    if s > 50 * 1024 * 1024:
                        out.append(_browser_cache_entry("Firefox", cache_p))
        except OSError:
            pass
        return out


class BraveCacheCleaner(Cleaner):
    name = "brave-cache"
    platforms = ("windows", "macos", "linux")
    description = "Brave browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        candidates = []
        if ctx.is_windows:
            candidates.append(os.path.join(ctx.home, "AppData", "Local",
                                            "BraveSoftware", "Brave-Browser",
                                            "User Data", "Default", "Cache"))
        elif ctx.is_macos:
            candidates.append(os.path.join(ctx.home, "Library", "Caches",
                                            "BraveSoftware", "Brave-Browser",
                                            "Default", "Cache"))
        elif ctx.is_linux:
            candidates.append(os.path.join(ctx.home, ".config", "BraveSoftware",
                                            "Brave-Browser", "Default", "Cache"))
        out = []
        for c in candidates:
            if os.path.isdir(c) and szd(c, 1, 5) > 50 * 1024 * 1024:
                out.append(_browser_cache_entry("Brave", c))
        return out


BROWSER_CLEANERS = [
    ChromeCacheCleaner,
    EdgeCacheCleaner,
    FirefoxCacheCleaner,
    BraveCacheCleaner,
]
