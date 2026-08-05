"""Cleaner plugin registry and runner.

Usage:
  from cleaners import REGISTRY, run_all
  from cleaners._base import ScanContext

  ctx = ScanContext.build()
  entries = run_all(ctx)        # list[Entry]
  # or, by category:
  sys_entries = run_all(ctx, categories={"system", "dev"})

Adding a new built-in cleaner:
  1. Drop a new file in `cleaners/` (e.g. `_mail.py`).
  2. Define a Cleaner subclass.
  3. Add the class to a *_CLEANERS list in that file.
  4. Import + register the list in `REGISTRY` below.
"""
from __future__ import annotations
from typing import Iterable, List, Set

from ._base import Cleaner, Entry, Result, ScanContext
from ._system import SYSTEM_CLEANERS
from ._browsers import BROWSER_CLEANERS
from ._dev import DEV_CLEANERS
from ._ide import IDE_CLEANERS
from ._cloud_chat import CLOUD_CHAT_CLEANERS
from ._vmware import VMwareCleaner
from ._extras import (
    GPU_CLEANERS, DEV_CLEANERS_EXTRA, CHAT_CLEANERS,
    BROWSER_CLEANERS_EXTRA,
)
# New cleaners (v9.0)
from ._communication import COMMUNICATION_CLEANERS
from ._browsers_extra import BROWSER_CLEANERS_EXTRA_NEW
from ._dev_extra import DEV_CLEANERS_EXTRA_NEW
from ._office import OFFICE_CLEANERS
from ._gaming import GAMING_CLEANERS
from ._deep_scan import DEEP_SCAN_CLEANERS
from ._windows_integration import WINDOWS_INTEGRATION_CLEANERS
from ._downloads_analyzer import DOWNLOADS_CLEANERS
from ._media import MEDIA_CLEANERS


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REGISTRY: List[type] = [
    # Original cleaners (v8.1)
    *SYSTEM_CLEANERS,         # 9: dumps, update, prefetch, etc.
    *GPU_CLEANERS,            # 1: GPU cache (NVIDIA/AMD/Intel)
    *BROWSER_CLEANERS,       # 4: Chrome/Edge/Firefox/Brave (cache only)
    *BROWSER_CLEANERS_EXTRA, # 1: full browser profile (advisory)
    *DEV_CLEANERS,           # 6: npm/yarn/pnpm/pip/cargo/misc
    *DEV_CLEANERS_EXTRA,     # 1: Docker data
    *IDE_CLEANERS,           # 2: VSCode/JetBrains
    *CLOUD_CHAT_CLEANERS,    # 3: OneDrive/Teams/Zoom
    *CHAT_CLEANERS,          # 3: WeChat/Tencent/DingTalk
    VMwareCleaner,           # 1: VMware VM detect + advisory
    # New cleaners (v9.0)
    *COMMUNICATION_CLEANERS,      # 5: Discord/Slack/Zoom/Skype/Telegram
    *BROWSER_CLEANERS_EXTRA_NEW,  # 6: Opera/Vivaldi/Chromium/LibreWolf/Waterfox/Arc
    *DEV_CLEANERS_EXTRA_NEW,      # 7: Java/Python/Vim/TortoiseSVN/Git/Ruby/Go
    *OFFICE_CLEANERS,             # 4: Office/LibreOffice/Thunderbird/Outlook
    *GAMING_CLEANERS,             # 4: Epic/GOG/EA/Ubisoft
    *DEEP_SCAN_CLEANERS,          # 7: .bak/.DS_Store/Thumbs.db/node_modules/venv/__pycache__/installers
    *WINDOWS_INTEGRATION_CLEANERS,# 7: Recent/Windows.old/Delivery/Defender/WER/Font/Icon
    *DOWNLOADS_CLEANERS,          # 3: Downloads analyzer/Temp/Recycle Bin
    *MEDIA_CLEANERS,              # 6: VLC/Spotify/Adobe/WinRAR/7-Zip/Everything
]
# Total: 63 built-in cleaners (was 24).


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def instantiate_all(filter_categories: Set[str] = None) -> List[Cleaner]:
    """Instantiate every registered cleaner (optionally filtered)."""
    out: List[Cleaner] = []
    for cls in REGISTRY:
        if filter_categories and cls.category not in filter_categories:
            continue
        try:
            out.append(cls())
        except Exception as e:
            # Bad plugin shouldn't kill the whole scan.
            from engine.utils import log
            log(f"Cleaner {cls.__name__} failed to instantiate: {e}", 0)
    return out


def run_all(ctx: ScanContext = None,
            categories: Set[str] = None) -> List[Entry]:
    """Run every cleaner's analyze() and return a flat list of Entry.

    Returns entries in the same shape as the legacy `scan_sys()`
    function in `engine.scanner`, so existing consumers
    (gen_actions) keep working.
    """
    if ctx is None:
        ctx = ScanContext.build()

    entries: List[Entry] = []
    for cleaner in instantiate_all(categories):
        if not cleaner.supported_on(ctx):
            continue
        try:
            entries.extend(cleaner.analyze(ctx))
        except Exception as e:
            from engine.utils import log
            log(f"Cleaner {cleaner.name} analyze() failed: {e}", 0)
    # Largest first
    entries.sort(key=lambda e: e.size_kb, reverse=True)
    return entries


__all__ = [
    "Cleaner", "Entry", "Result", "ScanContext",
    "REGISTRY", "instantiate_all", "run_all",
    "entry_to_legacy", "to_legacy_list",
]
from ._legacy_adapter import entry_to_legacy, to_legacy_list  # noqa: E402
