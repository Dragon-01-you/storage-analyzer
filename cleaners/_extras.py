"""GPU shader cache + Docker + Communication (chat) cleaners."""
from __future__ import annotations
import os
import shutil
import subprocess
from typing import List

from ._base import Cleaner, Entry, ScanContext
from engine.utils import szf, szd, _fast_szd, hk


def _exists(p: str) -> bool:
    return bool(p) and os.path.exists(p)


# ---------------------------------------------------------------------------
# GPU cache (NVIDIA / AMD / Intel)
# ---------------------------------------------------------------------------

class GPUCacheCleaner(Cleaner):
    name = "gpu-cache"
    platforms = ("windows",)
    risk_level = "none"
    description = "GPU shader caches (NVIDIA, AMD, Intel) - auto-rebuilt"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        out = []
        # NVIDIA
        for label, path in [
            ("NVIDIA Cache", os.path.join(ctx.home, "AppData", "Local", "NVIDIA",
                                          "DXCache")),
            ("NVIDIA Compute Cache", os.path.join(ctx.home, "AppData", "Local",
                                                  "NVIDIA", "GLCache")),
            ("NVIDIA Shader Cache", os.path.join(ctx.home, "AppData", "Roaming",
                                                 "NVIDIA", "shader_cache")),
        ]:
            if _exists(path) and os.path.isdir(path):
                s = _fast_szd(path, 10)
                if s > 1024 * 1024:
                    out.append(Entry(
                        name=label, path=path,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="GPU shader cache (auto-rebuilt)",
                        risk="none", prio=1, cat="system", safe=True,
                    ))
        # AMD
        amd = os.path.join(ctx.home, "AppData", "Local", "AMD")
        if _exists(amd) and os.path.isdir(amd):
            s = _fast_szd(amd, 10)
            if s > 1024 * 1024:
                out.append(Entry(
                    name="AMD Cache", path=amd,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="AMD driver cache (auto-rebuilt)",
                    risk="none", prio=1, cat="system", safe=True,
                ))
        # Intel
        intel = os.path.join(ctx.home, "AppData", "Local", "Intel")
        if _exists(intel) and os.path.isdir(intel):
            s = _fast_szd(intel, 10)
            if s > 1024 * 1024:
                out.append(Entry(
                    name="Intel Cache", path=intel,
                    size_kb=s // 1024, size_h=hk(s // 1024),
                    reason="Intel driver cache (auto-rebuilt)",
                    risk="none", prio=1, cat="system", safe=True,
                ))
        return out


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

class DockerCleaner(Cleaner):
    name = "docker-data"
    platforms = ("windows", "macos", "linux")
    risk_level = "med"   # deleting images forces re-pull; containers need re-run
    description = "Docker Desktop data dir (use 'docker system prune' for real cleanup)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        if ctx.is_windows:
            paths = [os.path.join(ctx.home, "AppData", "Local", "Docker")]
        elif ctx.is_macos:
            paths = [
                os.path.join(ctx.home, "Library", "Containers", "com.docker.docker"),
                os.path.join(ctx.home, "Library", "Group Containers", "group.com.docker"),
            ]
        else:
            paths = ["/var/lib/docker"]
        for p in paths:
            if _exists(p) and os.path.isdir(p):
                s = _fast_szd(p, 10)
                if s > 100 * 1024 * 1024:
                    out.append(Entry(
                        name="Docker Data", path=p,
                        size_kb=s // 1024, size_h=hk(s // 1024),
                        reason="Docker data (run 'docker system prune -a' for real cleanup)",
                        risk="med", prio=2, cat="dev", safe=False,
                    ))
        return out


# ---------------------------------------------------------------------------
# Communication: WeChat / Tencent / DingTalk
# ---------------------------------------------------------------------------

class WeChatCleaner(Cleaner):
    name = "wechat-cache"
    platforms = ("windows", "macos")
    risk_level = "med"  # caches are auto-rebuilt; chat history is NOT touched
    description = "WeChat cache directories (NOT chat history)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            # xwechat_files = new WeChat 4.x layout; WeChat Files = older 3.x
            candidates = [
                (os.path.join(ctx.home, "Documents", "xwechat_files"), "WeChat (xwechat)"),
                (os.path.join(ctx.home, "Documents", "WeChat Files"), "WeChat (3.x)"),
                (os.path.join(ctx.home, "AppData", "Local", "Tencent", "WeChat"), "WeChat Local"),
                (os.path.join(ctx.home, "AppData", "Roaming", "Tencent", "xwechat"),
                 "WeChat Roaming"),
            ]
        elif ctx.is_macos:
            candidates = [
                (os.path.join(ctx.home, "Library", "Containers", "com.tencent.xinWeChat"),
                 "WeChat macOS"),
            ]
        else:
            return []
        out = []
        for path, label in candidates:
            if not _exists(path):
                continue
            s = _fast_szd(path, 30)
            if s < 100 * 1024 * 1024:
                continue
            out.append(Entry(
                name=label, path=path,
                size_kb=s // 1024, size_h=hk(s // 1024),
                reason="WeChat data - cache auto-rebuilt, history kept",
                risk="med", prio=3, cat="chat", safe=False,
            ))
        return out


class TencentCleaner(Cleaner):
    name = "tencent-cache"
    platforms = ("windows",)
    risk_level = "med"
    description = "QQ / TIM cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if not ctx.is_windows:
            return []
        base = os.path.join(ctx.home, "AppData", "Roaming", "Tencent")
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 30)
        if s < 100 * 1024 * 1024:
            return []
        return [Entry(
            name="Tencent", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="QQ/TIM data - review before deleting",
            risk="med", prio=3, cat="chat", safe=False,
        )]


class DingTalkCleaner(Cleaner):
    name = "dingtalk-cache"
    platforms = ("windows", "macos")
    risk_level = "med"
    description = "DingTalk cache"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        if ctx.is_windows:
            base = os.path.join(ctx.home, "AppData", "Roaming", "DingTalk")
        elif ctx.is_macos:
            base = os.path.join(ctx.home, "Library", "Application Support", "DingTalk")
        else:
            return []
        if not _exists(base) or not os.path.isdir(base):
            return []
        s = _fast_szd(base, 15)
        if s < 100 * 1024 * 1024:
            return []
        return [Entry(
            name="DingTalk", path=base,
            size_kb=s // 1024, size_h=hk(s // 1024),
            reason="DingTalk data - review before deleting",
            risk="med", prio=3, cat="chat", safe=False,
        )]


# ---------------------------------------------------------------------------
# Browser FULL profile (not just cache) - advisory only
# ---------------------------------------------------------------------------

class BrowserProfileCleaner(Cleaner):
    name = "browser-profile"
    platforms = ("windows", "macos", "linux")
    risk_level = "med"  # deleting profile = loses passwords, history
    description = "Entire browser profile (NOT safe to auto-delete)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        out = []
        # Pull from PP["browsers"] for the OS
        browsers = ctx.pp.get("browsers", {}) or {}
        for bname, bpath in browsers.items():
            if not _exists(bpath) or not os.path.isdir(bpath):
                continue
            s = _fast_szd(bpath, 15)
            if s < 100 * 1024 * 1024:  # only flag >100MB profiles
                continue
            out.append(Entry(
                name=f"{bname} Profile", path=bpath,
                size_kb=s // 1024, size_h=hk(s // 1024),
                reason=f"{bname} full profile (cache + history + passwords). "
                       f"Only delete cache subdir, not whole profile.",
                risk="med", prio=3, cat="browser", safe=False,
            ))
        return out


GPU_CLEANERS = [GPUCacheCleaner]
DEV_CLEANERS_EXTRA = [DockerCleaner]
CHAT_CLEANERS = [WeChatCleaner, TencentCleaner, DingTalkCleaner]
BROWSER_CLEANERS_EXTRA = [BrowserProfileCleaner]
