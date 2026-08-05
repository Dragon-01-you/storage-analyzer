"""Windows system integration cleaners: MRU, recent docs, DNS cache, Windows.old, delivery optimization.

BleachBit's windows_explorer.xml covers these; we're adding parity.
"""
from __future__ import annotations
import os
import subprocess
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Windows Recent Documents
# ---------------------------------------------------------------------------

class RecentDocsCleaner(Cleaner):
    name = "recent-docs"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows recent documents list and jump lists"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Recent documents
        recent = os.path.join(ctx.home, "AppData", "Roaming", "Microsoft", "Windows", "Recent")
        if _exists(recent) and os.path.isdir(recent):
            s = _fast_szd(recent, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="Recent Documents", path=recent,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Windows recent documents list (safe to clear)",
                    risk="none", prio=3, cat="system", safe=True,
                ))
        # Jump lists
        jump = os.path.join(ctx.home, "AppData", "Roaming", "Microsoft", "Windows", "Recent",
                            "AutomaticDestinations")
        if _exists(jump) and os.path.isdir(jump):
            s = _fast_szd(jump, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="Jump Lists", path=jump,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Windows jump lists (auto-rebuilt)",
                    risk="none", prio=3, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Windows.old
# ---------------------------------------------------------------------------

class WindowsOldCleaner(Cleaner):
    name = "windows-old"
    platforms = ("windows",)
    risk_level = "med"
    category = "system"
    description = "Windows.old folder (previous Windows installation)"
    requires_privilege = True

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        windows_old = os.path.join(ctx.system_root, "..", "Windows.old")
        if not _exists(windows_old) or not os.path.isdir(windows_old):
            return []
        s = _fast_szd(windows_old, 5)
        if s < 1024 * 1024 * 1024:  # <1GB
            return []
        return [Entry(
            name="Windows.old",
            path=windows_old,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Previous Windows installation (cannot be restored after deletion)",
            risk="med", prio=1, cat="system", safe=False,
            needs_privilege=True,
        )]


# ---------------------------------------------------------------------------
# Delivery Optimization
# ---------------------------------------------------------------------------

class DeliveryOptimizationCleaner(Cleaner):
    name = "delivery-optimization"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows Delivery Optimization cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        do_path = os.path.join(ctx.system_root, "SoftwareDistribution", "DeliveryOptimization")
        if not _exists(do_path) or not os.path.isdir(do_path):
            return []
        s = _fast_szd(do_path, 5)
        if s < 100 * 1024 * 1024:  # <100MB
            return []
        return [Entry(
            name="Delivery Optimization",
            path=do_path,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Windows Update delivery cache (auto-rebuilt)",
            risk="none", prio=2, cat="system", safe=True,
        )]


# ---------------------------------------------------------------------------
# Windows Defender scan history
# ---------------------------------------------------------------------------

class DefenderHistoryCleaner(Cleaner):
    name = "defender-history"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows Defender scan history and quarantine"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        programdata = os.environ.get("ProgramData", "C:\\ProgramData")
        # Defender scan history
        defender_path = os.path.join(programdata, "Microsoft", "Windows Defender", "Scans", "History")
        if _exists(defender_path) and os.path.isdir(defender_path):
            s = _fast_szd(defender_path, 5)
            if s > 10 * 1024 * 1024:
                out.append(Entry(
                    name="Defender Scan History", path=defender_path,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Windows Defender scan history (safe to clear)",
                    risk="none", prio=3, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Windows Error Reporting
# ---------------------------------------------------------------------------

class ErrorReportingCleaner(Cleaner):
    name = "error-reporting"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows Error Reporting files"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        programdata = os.environ.get("ProgramData", "C:\\ProgramData")
        wer_path = os.path.join(programdata, "Microsoft", "Windows", "WER")
        if _exists(wer_path) and os.path.isdir(wer_path):
            for subdir in ["ReportArchive", "ReportQueue", "Temp"]:
                report_path = os.path.join(wer_path, subdir)
                if _exists(report_path) and os.path.isdir(report_path):
                    s = _fast_szd(report_path, 5)
                    if s > 10 * 1024 * 1024:
                        out.append(Entry(
                            name=f"WER {subdir}", path=report_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Windows Error Reporting (safe to clear)",
                            risk="none", prio=3, cat="system", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# Windows Font Cache
# ---------------------------------------------------------------------------

class FontCacheCleaner(Cleaner):
    name = "font-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows font cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        font_cache = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "Windows", "Fonts")
        if not _exists(font_cache) or not os.path.isdir(font_cache):
            return []
        s = _fast_szd(font_cache, 5)
        if s < 50 * 1024 * 1024:  # <50MB
            return []
        return [Entry(
            name="Font Cache", path=font_cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Windows font cache (auto-rebuilt on reboot)",
            risk="none", prio=3, cat="system", safe=True,
        )]


# ---------------------------------------------------------------------------
# Windows Icon Cache
# ---------------------------------------------------------------------------

class IconCacheCleaner(Cleaner):
    name = "icon-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "system"
    description = "Windows icon cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        icon_cache = os.path.join(ctx.home, "AppData", "Local", "Microsoft", "Windows", "Explorer",
                                  "iconcache_*.db")
        import glob
        files = glob.glob(icon_cache)
        if not files:
            return []
        total = sum(os.path.getsize(f) for f in files if _exists(f))
        if total < 10 * 1024 * 1024:  # <10MB
            return []
        return [Entry(
            name="Icon Cache",
            path=os.path.dirname(files[0]),
            size_kb=total // 1024, size_h=hk(total // 1024),
            reason="Windows icon cache (auto-rebuilt on reboot)",
            risk="none", prio=3, cat="system", safe=True,
        )]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

WINDOWS_INTEGRATION_CLEANERS = [
    RecentDocsCleaner,
    WindowsOldCleaner,
    DeliveryOptimizationCleaner,
    DefenderHistoryCleaner,
    ErrorReportingCleaner,
    FontCacheCleaner,
    IconCacheCleaner,
]
