"""Developer-toolchain cache cleaners.

These are safe by default: package caches are designed to be disposable
and get re-populated on next build. Going through the OS file system
is faster and more thorough than invoking the tool's own clean command,
which often leaves lock files behind.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import _fast_szd, hk


def _cache_entry(name: str, path: str, threshold_mb: int = 100) -> Entry:
    s = _fast_szd(path, timeout=10)
    kb = s // 1024
    return Entry(
        name=name, path=path, size_kb=kb, size_h=hk(kb),
        reason=f"{name} (regenerated on next install/build)",
        risk="none", prio=2, cat="dev", safe=True,
    )


def _add_if_big(out: List[Entry], name: str, path: str, threshold_mb: int = 100):
    if os.path.isdir(path) and _fast_szd(path, 5) > threshold_mb * 1024 * 1024:
        out.append(_cache_entry(name, path, threshold_mb))


class NpmCacheCleaner(Cleaner):
    name = "npm-cache"
    platforms = ("windows", "macos", "linux")
    description = "npm package cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [os.path.join(ctx.home, "AppData", "Local", "npm-cache")]
        else:
            paths = [os.path.join(ctx.home, ".npm", "_cacache")]
        for p in paths:
            _add_if_big(out, "npm Cache", p, 100)
        return out


class YarnCacheCleaner(Cleaner):
    name = "yarn-cache"
    platforms = ("windows", "macos", "linux")
    description = "Yarn classic / Berry cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [
                os.path.join(ctx.home, "AppData", "Local", "Yarn", "Cache"),
                os.path.join(ctx.home, "AppData", "Local", "Yarn", "berry"),
            ]
        else:
            paths = [
                os.path.join(ctx.home, ".cache", "yarn"),
                os.path.join(ctx.home, ".yarn", "cache"),
            ]
        for p in paths:
            _add_if_big(out, "Yarn Cache", p, 100)
        return out


class PnpmStoreCleaner(Cleaner):
    name = "pnpm-store"
    platforms = ("windows", "macos", "linux")
    description = "pnpm content-addressable store"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [
                os.path.join(ctx.home, "AppData", "Local", "pnpm", "store"),
            ]
        else:
            paths = [os.path.join(ctx.home, ".local", "share", "pnpm", "store")]
        for p in paths:
            _add_if_big(out, "pnpm Store", p, 100)
        return out


class PipCacheCleaner(Cleaner):
    name = "pip-cache"
    platforms = ("windows", "macos", "linux")
    description = "pip / uv wheel cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [os.path.join(ctx.home, "AppData", "Local", "pip", "cache")]
        else:
            paths = [os.path.join(ctx.home, ".cache", "pip"),
                     os.path.join(ctx.home, ".cache", "uv")]
        for p in paths:
            _add_if_big(out, "pip/uv Cache", p, 50)
        return out


class CargoCacheCleaner(Cleaner):
    name = "cargo-cache"
    platforms = ("windows", "macos", "linux")
    description = "Rust cargo registry + git checkouts"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [os.path.join(ctx.home, ".cargo", "registry", "cache"),
                     os.path.join(ctx.home, ".cargo", "registry", "src")]
        else:
            paths = [os.path.join(ctx.home, ".cargo", "registry", "cache"),
                     os.path.join(ctx.home, ".cargo", "registry", "src")]
        for p in paths:
            _add_if_big(out, "Cargo Cache", p, 100)
        return out


class NpmDevCacheCleaner(Cleaner):
    name = "dev-cache-misc"
    platforms = ("windows", "macos", "linux")
    description = "Other dev caches: .gradle, .m2, .nuget, .cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [
                (os.path.join(ctx.home, ".gradle"), "Gradle Cache", 200),
                (os.path.join(ctx.home, ".m2"), "Maven Cache", 200),
                (os.path.join(ctx.home, "AppData", "Local", "NuGet", "v3-cache"),
                 "NuGet Cache", 100),
                (os.path.join(ctx.home, "AppData", "Local", "Microsoft", "VisualStudio"),
                 "VS Component Cache", 200),
            ]
        else:
            paths = [
                (os.path.join(ctx.home, ".gradle"), "Gradle Cache", 200),
                (os.path.join(ctx.home, ".m2"), "Maven Cache", 200),
                (os.path.join(ctx.home, ".cache"), "Generic .cache", 200),
            ]
        for p, label, mb in paths:
            _add_if_big(out, label, p, mb)
        return out


DEV_CLEANERS = [
    NpmCacheCleaner,
    YarnCacheCleaner,
    PnpmStoreCleaner,
    PipCacheCleaner,
    CargoCacheCleaner,
    NpmDevCacheCleaner,
]
