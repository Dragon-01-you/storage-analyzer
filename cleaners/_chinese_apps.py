"""Chinese app cleaners: Baidu Netdisk, Aliwangwang, 360, Tencent Video, iQiyi, etc.

Targeting apps popular in China that BleachBit doesn't cover.
"""
from __future__ import annotations
import os
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# Baidu Netdisk (百度网盘)
# ---------------------------------------------------------------------------

class BaiduNetdiskCleaner(Cleaner):
    name = "baidu-netdisk"
    platforms = ("windows",)
    risk_level = "none"
    category = "cloud"
    description = "Baidu Netdisk cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Baidu Netdisk cache locations
        candidates = [
            (os.path.join(ctx.home, "AppData", "Local", "BaiduNetdisk"), "Baidu Netdisk Local"),
            (os.path.join(ctx.home, "AppData", "Roaming", "BaiduNetdisk"), "Baidu Netdisk Roaming"),
        ]
        for path, label in candidates:
            if not _exists(path):
                continue
            # Only clean cache subdirs
            for subdir in ["Cache", "cache", "Temp", "temp"]:
                cache_path = os.path.join(path, subdir)
                if _exists(cache_path) and os.path.isdir(cache_path):
                    s = _fast_szd(cache_path, 10)
                    if s > 100 * 1024 * 1024:  # >100MB
                        out.append(Entry(
                            name=f"{label} Cache", path=cache_path,
                            size_kb=s // 1024, size_h=hk(s // 1024),
                            reason="Baidu Netdisk cache (auto-rebuilt)",
                            risk="none", prio=2, cat="cloud", safe=True,
                        ))
        return out


# ---------------------------------------------------------------------------
# Aliwangwang (阿里旺旺)
# ---------------------------------------------------------------------------

class AliwangwangCleaner(Cleaner):
    name = "aliwangwang"
    platforms = ("windows",)
    risk_level = "none"
    category = "chat"
    description = "Aliwangwang cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Roaming", "Aliwangwang")
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 10)
        if s < 50 * 1024 * 1024:
            return []
        return [Entry(
            name="Aliwangwang", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Aliwangwang cache (review before deleting)",
            risk="none", prio=3, cat="chat", safe=True,
        )]


# ---------------------------------------------------------------------------
# 360 Browser
# ---------------------------------------------------------------------------

class Browser360Cleaner(Cleaner):
    name = "360-browser"
    platforms = ("windows",)
    risk_level = "none"
    category = "browser"
    description = "360 Browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        candidates = [
            (os.path.join(ctx.home, "AppData", "Local", "360Chrome", "Chrome", "User Data", "Default", "Cache"),
             "360 Chrome Cache"),
            (os.path.join(ctx.home, "AppData", "Local", "360Browser", "Browser", "User Data", "Default", "Cache"),
             "360 Browser Cache"),
        ]
        for path, label in candidates:
            if _exists(path) and os.path.isdir(path):
                s = _fast_szd(path, 10)
                if s > 50 * 1024 * 1024:
                    out.append(Entry(
                        name=label, path=path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="360 Browser cache (auto-rebuilt)",
                        risk="none", prio=2, cat="browser", safe=True,
                    ))
        return out


# ---------------------------------------------------------------------------
# QQ Browser
# ---------------------------------------------------------------------------

class QQBrowserCleaner(Cleaner):
    name = "qq-browser"
    platforms = ("windows",)
    risk_level = "none"
    category = "browser"
    description = "QQ Browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Local", "Tencent", "QQBrowser", "User Data", "Default", "Cache")
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 10)
        if s < 50 * 1024 * 1024:
            return []
        return [Entry(
            name="QQ Browser Cache", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="QQ Browser cache (auto-rebuilt)",
            risk="none", prio=2, cat="browser", safe=True,
        )]


# ---------------------------------------------------------------------------
# Sogou Browser
# ---------------------------------------------------------------------------

class SogouBrowserCleaner(Cleaner):
    name = "sogou-browser"
    platforms = ("windows",)
    risk_level = "none"
    category = "browser"
    description = "Sogou Browser cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Roaming", "SogouExplorer", "Webkit", "Cache")
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 10)
        if s < 50 * 1024 * 1024:
            return []
        return [Entry(
            name="Sogou Browser Cache", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Sogou Browser cache (auto-rebuilt)",
            risk="none", prio=2, cat="browser", safe=True,
        )]


# ---------------------------------------------------------------------------
# Tencent Video
# ---------------------------------------------------------------------------

class TencentVideoCleaner(Cleaner):
    name = "tencent-video"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "Tencent Video cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # Tencent Video cache
        cache = os.path.join(ctx.home, "AppData", "Local", "Tencent", "WeMeet", "Cache")
        if _exists(cache) and os.path.isdir(cache):
            s = _fast_szd(cache, 10)
            if s > 500 * 1024 * 1024:  # >500MB
                out.append(Entry(
                    name="Tencent Video Cache", path=cache,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Tencent Video cache (auto-rebuilt)",
                    risk="none", prio=2, cat="media", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# iQiyi
# ---------------------------------------------------------------------------

class IQiyiCleaner(Cleaner):
    name = "iqiyi"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "iQiyi cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        cache = os.path.join(ctx.home, "AppData", "Local", "iQiyi", "Cache")
        if not _exists(cache) or not os.path.isdir(cache):
            return []
        s = _fast_szd(cache, 10)
        if s < 500 * 1024 * 1024:
            return []
        return [Entry(
            name="iQiyi Cache", path=cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="iQiyi cache (auto-rebuilt)",
            risk="none", prio=2, cat="media", safe=True,
        )]


# ---------------------------------------------------------------------------
# Youku
# ---------------------------------------------------------------------------

class YoukuCleaner(Cleaner):
    name = "youku"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "Youku cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        cache = os.path.join(ctx.home, "AppData", "Local", "Youku", "Cache")
        if not _exists(cache) or not os.path.isdir(cache):
            return []
        s = _fast_szd(cache, 10)
        if s < 500 * 1024 * 1024:
            return []
        return [Entry(
            name="Youku Cache", path=cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Youku cache (auto-rebuilt)",
            risk="none", prio=2, cat="media", safe=True,
        )]


# ---------------------------------------------------------------------------
# Bilibili
# ---------------------------------------------------------------------------

class BilibiliCleaner(Cleaner):
    name = "bilibili"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "Bilibili cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        cache = os.path.join(ctx.home, "AppData", "Local", "Packages",
                            "36699Atelier39.forPHH_q5va0y3e5e9t0", "LocalCache")
        if not _exists(cache) or not os.path.isdir(cache):
            # Try alternative path
            cache = os.path.join(ctx.home, "AppData", "Local", "Bilibili", "Cache")
        if not _exists(cache) or not os.path.isdir(cache):
            return []
        s = _fast_szd(cache, 10)
        if s < 500 * 1024 * 1024:
            return []
        return [Entry(
            name="Bilibili Cache", path=cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Bilibili cache (auto-rebuilt)",
            risk="none", prio=2, cat="media", safe=True,
        )]


# ---------------------------------------------------------------------------
# NetEase Cloud Music
# ---------------------------------------------------------------------------

class NetEaseMusicCleaner(Cleaner):
    name = "netease-music"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "NetEase Cloud Music cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        cache = os.path.join(ctx.home, "AppData", "Local", "NetEase", "CloudMusic", "Cache")
        if not _exists(cache) or not os.path.isdir(cache):
            return []
        s = _fast_szd(cache, 10)
        if s < 500 * 1024 * 1024:
            return []
        return [Entry(
            name="NetEase Music Cache", path=cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="NetEase Cloud Music cache (auto-rebuilt)",
            risk="none", prio=2, cat="media", safe=True,
        )]


# ---------------------------------------------------------------------------
# Kuwo Music
# ---------------------------------------------------------------------------

class KuwoMusicCleaner(Cleaner):
    name = "kuwo-music"
    platforms = ("windows",)
    risk_level = "none"
    category = "media"
    description = "Kuwo Music cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        cache = os.path.join(ctx.home, "AppData", "Local", "Kuwo", "Cache")
        if not _exists(cache) or not os.path.isdir(cache):
            return []
        s = _fast_szd(cache, 10)
        if s < 500 * 1024 * 1024:
            return []
        return [Entry(
            name="Kuwo Music Cache", path=cache,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="Kuwo Music cache (auto-rebuilt)",
            risk="none", prio=2, cat="media", safe=True,
        )]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

CHINESE_APP_CLEANERS = [
    BaiduNetdiskCleaner,
    AliwangwangCleaner,
    Browser360Cleaner,
    QQBrowserCleaner,
    SogouBrowserCleaner,
    TencentVideoCleaner,
    IQiyiCleaner,
    YoukuCleaner,
    BilibiliCleaner,
    NetEaseMusicCleaner,
    KuwoMusicCleaner,
]
