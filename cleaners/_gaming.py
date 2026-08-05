"""Gaming platform cleaners: Epic Games, GOG Galaxy, Origin, Ubisoft Connect.

Steam is already covered in _extras.py.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Epic Games Store
# ---------------------------------------------------------------------------

class EpicGamesCleaner(Cleaner):
    name = "epic-games"
    platforms = ("windows",)
    risk_level = "med"
    category = "gaming"
    description = "Epic Games Store cache and shader cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Epic Games cache
        epic_cache = os.path.join(ctx.home, "AppData", "Local", "EpicGamesLauncher", "Saved", "webcache")
        if _exists(epic_cache) and os.path.isdir(epic_cache):
            s = _fast_szd(epic_cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="Epic Games Cache", path=epic_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Epic Games launcher cache (auto-rebuilt)",
                    risk="none", prio=2, cat="gaming", safe=True,
                ))
        # Epic Games shader cache
        for label, path in [
            ("Epic Shader Cache", os.path.join(ctx.home, "AppData", "Local", "UnrealEngine", "ShaderCache")),
            ("Epic Derived Data", os.path.join(ctx.home, "AppData", "Local", "UnrealEngine", "DerivedDataCache")),
        ]:
            if _exists(path) and os.path.isdir(path):
                s = _fast_szd(path, 10)
                if s > 100 * 1024 * 1024:
                    out.append(Entry(
                        name=label, path=path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason=f"{label} (auto-rebuilt by games)",
                        risk="none", prio=2, cat="gaming", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# GOG Galaxy
# ---------------------------------------------------------------------------

class GOGGalaxyCleaner(Cleaner):
    name = "gog-galaxy"
    platforms = ("windows",)
    risk_level = "med"
    category = "gaming"
    description = "GOG Galaxy cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Local", "GOG.com", "Galaxy")
        if not _exists(base) or not os.path.isdir(base):
            return []
        out = []
        for subdir in ["cache", "webcache", "Logs"]:
            cache_path = os.path.join(base, subdir)
            if _exists(cache_path) and os.path.isdir(cache_path):
                s = _fast_szd(cache_path, 10)
                if s > 50 * 1024 * 1024:
                    out.append(Entry(
                        name=f"GOG Galaxy {subdir.title()}", path=cache_path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="GOG Galaxy cache (auto-rebuilt)",
                        risk="none", prio=2, cat="gaming", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# EA App (formerly Origin)
# ---------------------------------------------------------------------------

class EACleaner(Cleaner):
    name = "ea-app"
    platforms = ("windows",)
    risk_level = "med"
    category = "gaming"
    description = "EA App (Origin) cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # EA App cache
        ea_cache = os.path.join(ctx.home, "AppData", "Local", "Electronic Arts", "EA Desktop", "cache")
        if _exists(ea_cache) and os.path.isdir(ea_cache):
            s = _fast_szd(ea_cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="EA App Cache", path=ea_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="EA App cache (auto-rebuilt)",
                    risk="none", prio=2, cat="gaming", safe=True,
                ))
        # Origin cache (legacy)
        origin_cache = os.path.join(ctx.home, "AppData", "Local", "Origin")
        if _exists(origin_cache) and os.path.isdir(origin_cache):
            s = _fast_szd(origin_cache, 10)
            if s > 100 * 1024 * 1024:
                out.append(Entry(
                    name="Origin Cache", path=origin_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Origin cache (legacy, safe to clear)",
                    risk="none", prio=2, cat="gaming", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Ubisoft Connect
# ---------------------------------------------------------------------------

class UbisoftConnectCleaner(Cleaner):
    name = "ubisoft-connect"
    platforms = ("windows",)
    risk_level = "med"
    category = "gaming"
    description = "Ubisoft Connect cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Local", "Ubisoft Game Launcher")
        if not _exists(base) or not os.path.isdir(base):
            return []
        out = []
        for subdir in ["cache", "logs"]:
            cache_path = os.path.join(base, subdir)
            if _exists(cache_path) and os.path.isdir(cache_path):
                s = _fast_szd(cache_path, 10)
                if s > 50 * 1024 * 1024:
                    out.append(Entry(
                        name=f"Ubisoft {subdir.title()}", path=cache_path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="Ubisoft Connect cache (auto-rebuilt)",
                        risk="none", prio=2, cat="gaming", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

GAMING_CLEANERS = [
    EpicGamesCleaner,
    GOGGalaxyCleaner,
    EACleaner,
    UbisoftConnectCleaner,
]
