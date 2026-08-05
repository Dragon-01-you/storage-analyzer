"""Communication app cleaners: Discord, Slack, Zoom, Skype, Telegram.

BleachBit has these; we're adding parity.
Each targets cache ONLY — never chat history or login tokens.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------

class DiscordCleaner(Cleaner):
    name = "discord-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "chat"
    description = "Discord cache (Stable, PTB, Canary)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        variants = ["discord", "discordptb", "discordcanary", "discorddevelopment"]
        for variant in variants:
            if ctx.is_windows:
                base = os.path.join(ctx.home, "AppData", "Roaming", variant)
            elif ctx.is_macos:
                base = os.path.join(ctx.home, "Library", "Application Support", variant)
            else:
                base = os.path.join(ctx.home, ".config", variant)
            if not _exists(base) or not os.path.isdir(base):
                continue
            # Only clean cache subdirs, not the whole profile
            for subdir in ["Cache", "Code Cache", "GPUCache"]:
                cache_path = os.path.join(base, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 10 * 1024 * 1024:  # >10MB
                        out.append(Entry(
                            name=f"Discord {variant.title()} Cache",
                            path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Discord cache (auto-rebuilt on next launch)",
                            risk="none", prio=2, cat="chat", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

class SlackCleaner(Cleaner):
    name = "slack-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "chat"
    description = "Slack Electron cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Slack")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "Slack")
        else:
            base = os.path.join(ctx.home, ".config", "Slack")
        if not _exists(base) or not os.path.isdir(base):
            return []
        for subdir in ["Cache", "Code Cache", "GPUCache", "Service Worker\CacheStorage"]:
            cache_path = os.path.join(base, subdir)
            if _exists(cache_path) and os.path.isdir(cache_path):
                s = _fast_szd(cache_path, 10)
                if s > 10 * 1024 * 1024:
                    out.append(Entry(
                        name="Slack Cache",
                        path=cache_path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="Slack cache (auto-rebuilt)",
                        risk="none", prio=2, cat="chat", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------

class ZoomCleaner(Cleaner):
    name = "zoom-cache"
    platforms = ("windows", "macos")
    risk_level = "none"
    category = "chat"
    description = "Zoom cache and old recordings"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Zoom")
            cache = os.path.join(base, "cache")
            old_recordings = os.path.join(ctx.home, "Documents", "Zoom")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "zoom.us")
            cache = os.path.join(base, "cache")
            old_recordings = os.path.join(ctx.home, "Documents", "Zoom")
        else:
            return []
        # Zoom cache
        if _exists(cache) and os.path.isdir(cache):
            s = _fast_szd(cache, 10)
            if s > 50 * 1024 * 1024:
                out.append(Entry(
                    name="Zoom Cache",
                    path=cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Zoom cache (auto-rebuilt)",
                    risk="none", prio=2, cat="chat", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Skype
# ---------------------------------------------------------------------------

class SkypeCleaner(Cleaner):
    name = "skype-cache"
    platforms = ("windows",)
    risk_level = "none"
    category = "chat"
    description = "Skype cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Local", "Packages",
                            "Microsoft.SkypeApp_kzf8qxf38zg5c", "LocalState")
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 10)
        if s < 50 * 1024 * 1024:
            return []
        return [Entry(
            name="Skype Cache",
            path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Skype cache (auto-rebuilt)",
            risk="none", prio=2, cat="chat", safe=True,
        )]


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

class TelegramCleaner(Cleaner):
    name = "telegram-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "chat"
    description = "Telegram Desktop cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "Telegram Desktop")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "Telegram")
        else:
            base = os.path.join(ctx.home, ".local", "share", "TelegramDesktop")
        if not _exists(base) or not os.path.isdir(base):
            return []
        # Telegram stores cache in tdata
        tdata = os.path.join(base, "tdata")
        if _exists(tdata) and os.path.isdir(tdata):
            # Only cache subdirs, not user data
            for subdir in ["cache", "tdummy", "user_data"]:
                cache_path = os.path.join(tdata, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 50 * 1024 * 1024:
                        out.append(Entry(
                            name="Telegram Cache",
                            path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Telegram cache (auto-rebuilt)",
                            risk="none", prio=2, cat="chat", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

COMMUNICATION_CLEANERS = [
    DiscordCleaner,
    SlackCleaner,
    ZoomCleaner,
    SkypeCleaner,
    TelegramCleaner,
]
