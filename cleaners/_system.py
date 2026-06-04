"""Windows system-level cleaners: temp dumps, update cache, prefetch, etc.

These are all the things BleachBit puts under "System" / "Windows".
Each runs only on Windows and reports size via the fast_szd helper.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szf, szd, _fast_szd, hk, IS_WIN


def _exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)


def _entry(name: str, path: str, reason: str, size_bytes: int,
           *, cat="system", risk="none", prio=1, safe=True,
           needs_recycle=False, needs_dism=False) -> Entry:
    kb = size_bytes // 1024
    return Entry(
        name=name, path=path, size_kb=kb, size_h=hk(kb),
        reason=reason, risk=risk, prio=prio, cat=cat, safe=safe,
        needs_recycle=needs_recycle, needs_dism=needs_dism,
    )


class MemoryDumpCleaner(Cleaner):
    name = "memory-dump"
    platforms = ("windows",)
    risk_level = "none"
    description = "C:\\Windows\\MEMORY.DMP and minidumps"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        for key, label in (("memory_dmp", "MEMORY.DMP"), ("minidump", "Minidump")):
            p = ctx.pp.get(key, "")
            if _exists(p) and os.path.isfile(p):
                out.append(_entry(label, p, "System memory dump", szf(p), prio=1))
            elif _exists(p) and os.path.isdir(p):
                s = szd(p, 1, 5)
                if s > 1024 * 1024:
                    out.append(_entry(label, p, "Minidump directory", s, prio=1))
        return out


class WindowsUpdateCacheCleaner(Cleaner):
    name = "windows-update-cache"
    platforms = ("windows",)
    risk_level = "none"
    description = "CBS logs, WU Download cache, Delivery Optimization"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        for key, label, reason, depth in [
            ("cbs_logs", "CBS Logs", "Component-Based Servicing logs", 2),
            ("wu_cache", "Windows Update Cache", "Update downloads", 2),
        ]:
            p = ctx.pp.get(key, "")
            if _exists(p) and os.path.isdir(p):
                s = szd(p, depth, 10)
                if s > 1024 * 1024:
                    out.append(_entry(label, p, reason, s))
        # Delivery Optimization
        do = os.path.join(ctx.system_root, "SoftwareDistribution", "DeliveryOptimization")
        if _exists(do) and os.path.isdir(do):
            s = szd(do, 2, 10)
            if s > 1024 * 1024:
                out.append(_entry("Delivery Optimization", do,
                                   "Windows Update delivery cache", s))
        return out


class PrefetchCleaner(Cleaner):
    name = "prefetch"
    platforms = ("windows",)
    risk_level = "none"
    description = "C:\\Windows\\Prefetch (auto-rebuilds)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        p = ctx.pp.get("prefetch", "")
        if not (_exists(p) and os.path.isdir(p)):
            return []
        s = szd(p, 1, 5)
        if s < 1024 * 1024:
            return []
        return [_entry("Prefetch", p, "Prefetch cache (auto-rebuilt)", s)]


class CrashDumpsCleaner(Cleaner):
    name = "crash-dumps"
    platforms = ("windows",)
    risk_level = "none"
    description = "%LOCALAPPDATA%\\CrashDumps"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        p = ctx.pp.get("crash_dumps", "")
        if not (_exists(p) and os.path.isdir(p)):
            return []
        s = szd(p, 2, 10)
        if s < 1024 * 1024:
            return []
        return [_entry("CrashDumps", p, "Crash dumps", s)]


class ThumbnailCacheCleaner(Cleaner):
    name = "thumbnail-cache"
    platforms = ("windows",)
    risk_level = "none"
    description = "Explorer thumbcache_*.db + iconcache_*.db (auto-rebuilt)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        thumb_dir = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "Windows", "Explorer")
        if not (_exists(thumb_dir) and os.path.isdir(thumb_dir)):
            return []
        total = 0
        try:
            for f in os.listdir(thumb_dir):
                if f.lower().startswith(("thumbcache", "iconcache")):
                    total += szf(os.path.join(thumb_dir, f))
        except OSError:
            return []
        if total < 1024 * 1024:
            return []
        return [_entry("Thumbnail Cache", thumb_dir,
                       "Explorer thumbnail/icon cache (auto-rebuilt)", total)]


class ErrorReportsCleaner(Cleaner):
    name = "error-reports"
    platforms = ("windows",)
    risk_level = "none"
    description = "%ProgramData%\\Microsoft\\Windows\\WER"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        wer = os.path.join(
            os.environ.get("ProgramData", "C:\\ProgramData"),
            "Microsoft", "Windows", "WER"
        )
        if not (_exists(wer) and os.path.isdir(wer)):
            return []
        s = szd(wer, 3, 10)
        if s < 1024 * 1024:
            return []
        return [_entry("Error Reports", wer, "Windows Error Reporting data", s)]


class WinSxSCleaner(Cleaner):
    name = "winsxs"
    platforms = ("windows",)
    risk_level = "none"
    requires_privilege = True
    description = "Component store - uses DISM StartComponentCleanup"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        p = os.path.join(ctx.system_root, "WinSxS")
        if not (_exists(p) and os.path.isdir(p)):
            return []
        s = szd(p, 2, 15)
        if s < 1024 * 1024 * 1024:  # < 1GB, skip
            return []
        return [_entry("WinSxS Component Store", p,
                       "Windows component store - use DISM", s,
                       needs_dism=True, prio=1)]


class RecycleBinCleaner(Cleaner):
    name = "recycle-bin"
    platforms = ("windows",)
    risk_level = "none"
    description = "Empty the Recycle Bin (user-driven)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        try:
            import ctypes
            from ctypes import wintypes
            class SHQUERYRBINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("i64Size", ctypes.c_int64),
                    ("i64NumItems", ctypes.c_int64),
                ]
            info = SHQUERYRBINFO()
            info.cbSize = ctypes.sizeof(info)
            hr = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
            if hr == 0 and info.i64Size > 0:
                return [Entry(
                    name="Recycle Bin", path="Recycle Bin",
                    size_kb=info.i64Size // 1024,
                    size_h=hk(info.i64Size // 1024),
                    reason="Recycle Bin contents",
                    risk="none", prio=1, cat="system",
                    safe=True, needs_recycle=True,
                )]
        except Exception:
            pass
        return []


class WindowsOldCleaner(Cleaner):
    name = "windows-old"
    platforms = ("windows",)
    risk_level = "med"  # user might want to roll back
    description = "Previous Windows installation (post-upgrade)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        # SystemRoot is C:\Windows, so the parent is C:\
        drive = ctx.system_root.rstrip("\\").rsplit("\\", 1)[0] or "C:\\"
        p = os.path.join(drive, "Windows.old")
        if not (_exists(p) and os.path.isdir(p)):
            return []
        s = szd(p, 2, 15)
        if s < 1024 * 1024 * 1024:
            return []
        return [_entry("Windows.old", p,
                       "Previous Windows installation (review)",
                       s, risk="med")]


# All system cleaners in this file
SYSTEM_CLEANERS = [
    MemoryDumpCleaner,
    WindowsUpdateCacheCleaner,
    PrefetchCleaner,
    CrashDumpsCleaner,
    ThumbnailCacheCleaner,
    ErrorReportsCleaner,
    WinSxSCleaner,
    RecycleBinCleaner,
    WindowsOldCleaner,
]
