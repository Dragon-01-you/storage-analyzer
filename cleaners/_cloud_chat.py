"""Cloud sync + video-conferencing cache cleaners.

Caches are safe to clear; they re-download lazily. Do NOT touch the
actual sync root (e.g. ~/OneDrive/Documents).
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import _fast_szd, szd, hk


class OneDriveCacheCleaner(Cleaner):
    name = "onedrive-cache"
    platforms = ("windows", "macos",)
    description = "OneDrive local sync cache (NOT the sync root)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "OneDrive")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "com.microsoft.OneDrive")
        else:
            return []
        if not os.path.isdir(base):
            return []
        s = _fast_szd(base, timeout=10)
        if s < 1024 * 1024 * 1024:  # < 1GB
            return []
        return [Entry(
            name="OneDrive Cache", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="OneDrive local cache (re-downloaded on demand)",
            risk="none", prio=2, cat="cloud", safe=True,
        )]


class TeamsCacheCleaner(Cleaner):
    name = "teams-cache"
    platforms = ("windows", "macos", "linux")
    description = "Microsoft Teams cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Microsoft", "Teams")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Group Containers",
                                 "UBF8T346G9.com.microsoft.teams")
        else:
            base = os.path.join(ctx.home, ".config", "Microsoft", "Microsoft Teams")
        if not os.path.isdir(base):
            return []
        out = []
        for sub, label in (("Cache", "Teams Cache"),
                            ("GPUCache", "Teams GPU Cache"),
                            ("blob_storage", "Teams Blob Storage"),
                            ("dat", "Teams dat")):
            p = os.path.join(base, sub)
            if os.path.isdir(p):
                s = _fast_szd(p, 10)
                if s > 100 * 1024 * 1024:
                    out.append(Entry(
                        name=f"Teams {label}",
                        path=p,
                        size_kb=s // 1024,
                        size_h=hk(s // 1024),
                        reason=f"Teams {label} (auto-rebuilt)",
                        risk="none", prio=2, cat="chat", safe=True,
                    ))
        return out


class ZoomCacheCleaner(Cleaner):
    name = "zoom-cache"
    platforms = ("windows", "macos",)
    description = "Zoom video cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Zoom")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "us.zoom.xos")
        else:
            return []
        if not os.path.isdir(base):
            return []
        out = []
        for sub in ("data", "bin", "cache"):
            p = os.path.join(base, sub)
            if os.path.isdir(p):
                s = _fast_szd(p, 5)
                if s > 50 * 1024 * 1024:
                    out.append(Entry(
                        name=f"Zoom {sub} cache",
                        path=p,
                        size_kb=s // 1024,
                        size_h=hk(s // 1024),
                        reason=f"Zoom {sub} (auto-rebuilt)",
                        risk="none", prio=2, cat="chat", safe=True,
                    ))
        return out


CLOUD_CHAT_CLEANERS = [
    OneDriveCacheCleaner,
    TeamsCacheCleaner,
    ZoomCacheCleaner,
]
