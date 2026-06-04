"""IDE cache cleaners: VS Code, JetBrains, Eclipse, Sublime.

VS Code cache is safe to clear; JetBrains caches are heavy but
rebuild automatically on next index.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import _fast_szd, szd, hk


def _ide_entry(name: str, path: str, *, threshold_mb: int = 100) -> Entry:
    s = _fast_szd(path, timeout=15) if "JetBrains" in name else szd(path, 4, 30)
    kb = s // 1024
    return Entry(
        name=name, path=path, size_kb=kb, size_h=hk(kb),
        reason=f"{name} (auto-rebuilt on next launch)",
        risk="none", prio=2, cat="ide", safe=True,
    )


class VSCodeCacheCleaner(Cleaner):
    name = "vscode-cache"
    platforms = ("windows", "macos", "linux")
    description = "VS Code cache directories (Caches, Code Cache, GPUCache)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Code")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "Code")
        else:
            base = os.path.join(ctx.home, ".config", "Code")
        for sub in ("Cache", "Code Cache", "GPUCache", "CachedData"):
            _p = os.path.join(base, sub)
            if os.path.isdir(_p):
                s = _fast_szd(_p, 10)
                if s > 100 * 1024 * 1024:
                    out.append(Entry(
                        name=f"VS Code {sub}",
                        path=_p,
                        size_kb=s // 1024,
                        size_h=hk(s // 1024),
                        reason=f"VS Code {sub} (auto-rebuilt)",
                        risk="none", prio=2, cat="ide", safe=True,
                    ))
        return out


class JetBrainsCacheCleaner(Cleaner):
    name = "jetbrains-cache"
    platforms = ("windows", "macos", "linux")
    description = "JetBrains IDE caches (IntelliJ, PyCharm, GoLand, etc.)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Local", "JetBrains")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Caches", "JetBrains")
        else:
            base = os.path.join(ctx.home, ".cache", "JetBrains")
        if not os.path.isdir(base):
            return []
        s = _fast_szd(base, timeout=30)
        if s < 1024 * 1024 * 1024:  # < 1GB, skip
            return []
        return [_ide_entry("JetBrains Cache", base, threshold_mb=1024)]


IDE_CLEANERS = [
    VSCodeCacheCleaner,
    JetBrainsCacheCleaner,
]
