"""Extra dev tool cleaners: Java, Python, Vim, TortoiseSVN, Git, Ruby, Go.

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
# Java cache
# ---------------------------------------------------------------------------

class JavaCacheCleaner(Cleaner):
    name = "java-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Java runtime cache and deployment cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            candidates = [
                (os.path.join(ctx.home, "AppData", "LocalLow", "Sun", "Java", "Deployment"),
                 "Java Deployment Cache"),
                (os.path.join(ctx.home, "AppData", "Local", "Oracle", "Java"),
                 "Oracle Java Cache"),
            ]
        elif ctx.is_macos:
            candidates = [
                (os.path.join(ctx.home, "Library", "Caches", "Java"),
                 "Java Cache"),
            ]
        else:
            candidates = [
                (os.path.join(ctx.home, ".java", "deployment"),
                 "Java Deployment Cache"),
                (os.path.join(ctx.home, ".cache", "icedtea-web"),
                 "IcedTea Cache"),
            ]
        for path, label in candidates:
            if _exists(path) and os.path.isdir(path):
                s = _fast_szd(path, 10)
                if s > 10 * 1024 * 1024:
                    out.append(Entry(
                        name=label, path=path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="Java cache (auto-rebuilt)",
                        risk="none", prio=2, cat="dev", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# Python __pycache__ and .pyc
# ---------------------------------------------------------------------------

class PythonCacheCleaner(Cleaner):
    name = "python-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Python __pycache__ and .pyc files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        # Global pip cache
        if ctx.is_windows:
            pip_cache = os.path.join(ctx.home, "AppData", "Local", "pip", "cache")
        elif ctx.is_macos:
            pip_cache = os.path.join(ctx.home, "Library", "Caches", "pip")
        else:
            pip_cache = os.path.join(ctx.home, ".cache", "pip")
        if _exists(pip_cache) and os.path.isdir(pip_cache):
            s = _fast_szd(pip_cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="pip Cache", path=pip_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="pip download cache (auto-rebuilt on next install)",
                    risk="none", prio=2, cat="dev", safe=True,
                ))
        # uv cache
        if ctx.is_windows:
            uv_cache = os.path.join(ctx.home, "AppData", "Local", "uv", "cache")
        else:
            uv_cache = os.path.join(ctx.home, ".cache", "uv")
        if _exists(uv_cache) and os.path.isdir(uv_cache):
            s = _fast_szd(uv_cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="uv Cache", path=uv_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="uv package cache (auto-rebuilt)",
                    risk="none", prio=2, cat="dev", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Vim swap files
# ---------------------------------------------------------------------------

class VimSwapCleaner(Cleaner):
    name = "vim-swap"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Vim swap and backup files (.swp, .swo, .swn, ~)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        # Scan home directory for vim swap files
        try:
            for root, dirs, files in os.walk(ctx.home):
                # Skip deep directories
                depth = root.replace(ctx.home, '').count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                for f in files:
                    if f.endswith(('.swp', '.swo', '.swn')) or f.endswith('~'):
                        fp = os.path.join(root, f)
                        try:
                            s = os.path.getsize(fp)
                            if s > 1024:  # >1KB
                                out.append(Entry(
                                    name=f"Vim: {f}",
                                    path=fp,
                                    size_kb=s // 1024, size_h=hk(s // 1024),
                                    reason="Vim swap/backup file (safe if editor is closed)",
                                    risk="none", prio=3, cat="dev", safe=True,
                                ))
                        except OSError:
                            pass
        except OSError:
            pass
        return out


# ---------------------------------------------------------------------------
# TortoiseSVN cache
# ---------------------------------------------------------------------------

class TortoiseSVNCacheCleaner(Cleaner):
    name = "tortoisesvn-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "dev"
    description = "TortoiseSVN cache and status cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # TortoiseSVN status cache
        cache_path = os.path.join(ctx.home, "AppData", "Local", "TSVNCache")
        if _exists(cache_path) and os.path.isdir(cache_path):
            s = _fast_szd(cache_path, 10)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="TortoiseSVN Cache", path=cache_path,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="TortoiseSVN status cache (auto-rebuilt)",
                    risk="none", prio=2, cat="dev", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Git cache
# ---------------------------------------------------------------------------

class GitCacheCleaner(Cleaner):
    name = "git-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Git credential cache and temp files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        # Git credential cache
        if ctx.is_windows:
            git_credential = os.path.join(ctx.home, "AppData", "Local", "Git", "CredentialCache")
        else:
            git_credential = os.path.join(ctx.home, ".git-credential-cache")
        if _exists(git_credential) and os.path.isdir(git_credential):
            s = _fast_szd(git_credential, 5)
            if s > 1024 * 1024:
                out.append(Entry(
                    name="Git Credential Cache", path=git_credential,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Git credential cache (safe to clear)",
                    risk="none", prio=2, cat="dev", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Ruby gems cache
# ---------------------------------------------------------------------------

class RubyCacheCleaner(Cleaner):
    name = "ruby-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Ruby gems cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            gem_cache = os.path.join(ctx.home, "AppData", "Local", "gem", "cache")
        else:
            gem_cache = os.path.join(ctx.home, ".gem", "cache")
        if _exists(gem_cache) and os.path.isdir(gem_cache):
            s = _fast_szd(gem_cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="Ruby Gems Cache", path=gem_cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Ruby gems cache (auto-rebuilt on next install)",
                    risk="none", prio=2, cat="dev", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Go module cache
# ---------------------------------------------------------------------------

class GoCacheCleaner(Cleaner):
    name = "go-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "Go module and build cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            go_cache = os.path.join(ctx.home, "AppData", "Local", "go-build")
            go_mod = os.path.join(ctx.home, "go", "pkg", "mod")
        else:
            go_cache = os.path.join(ctx.home, ".cache", "go-build")
            go_mod = os.path.join(ctx.home, "go", "pkg", "mod")
        for label, path in [("Go Build Cache", go_cache), ("Go Module Cache", go_mod)]:
            if _exists(path) and os.path.isdir(path):
                s = _fast_szd(path, 10)
                if s > 100 * 1024 * 1024:
                    out.append(Entry(
                        name=label, path=path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason=f"{label} (auto-rebuilt on next build)",
                        risk="none", prio=2, cat="dev", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

DEV_CLEANERS_EXTRA_NEW = [
    JavaCacheCleaner,
    PythonCacheCleaner,
    VimSwapCleaner,
    TortoiseSVNCacheCleaner,
    GitCacheCleaner,
    RubyCacheCleaner,
    GoCacheCleaner,
]
