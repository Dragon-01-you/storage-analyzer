"""AI Brain: Intent Parser + Cognitive Adapter (3-level labeling).

This is the ONLY module that ever produces text intended for the user.
Every string that crosses the module boundary is `human_readable_*`.
Technical names stay in `technical_*` fields for audit only.

Anti-foolhardy-by-design:
  - We never display .tmp / .iso / node_modules to the user.
  - When in doubt, we say "未知的大型应用数据" rather than guessing.
  - The default action for an unrecognized item is REVIEW, not delete.

v8.1 enhancements:
  - 40+ L1 fingerprint rules covering browsers, IDE, cloud sync, games, etc.
  - Improved intent parser with more natural language patterns
  - _h() helper consolidated here (single source of truth)
"""
from __future__ import annotations
import fnmatch
import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .types import (
    ScanConfig, DirectorySummary, CleanEntry, CognitiveLabel,
    LabelSource, RiskLevel,
    DeletionMode, _human_bytes,
)


# ===========================================================================
# 1. Intent Parser — natural language → ScanConfig
# ===========================================================================

class IntentParser:
    """Turn "清理C盘，保留原神" into a structured ScanConfig.

    Two-stage:
      1. Rule-based extraction (paths, keywords, action words)
      2. Optional LLM refinement for ambiguous cases

    The rule-based stage is intentionally conservative: it only sets
    fields it's SURE about. Ambiguity → field is left as default,
    which is the safest possible ScanConfig (DRY_RUN, no exclusions,
    no specific paths → scan everything that's standard).
    """

    _DRIVE_PATTERNS = [
        re.compile(r"([CDEFG]:\\?|/[a-z])", re.IGNORECASE),
    ]
    _KEEP_HINTS = [
        re.compile(r"(保留|留着|不要删|不要清理|保留\s*)(.+)", re.IGNORECASE),
        re.compile(r"(keep|preserve|save|don't delete|don\u2019t delete)\s+(.+)", re.IGNORECASE),
    ]
    _CLEAN_HINTS = [
        re.compile(r"(清理|清空|删除|删掉|扫一扫|整理|瘦身|释放)\s*(.*)", re.IGNORECASE),
        re.compile(r"(clean|free up|tidy|reclaim|scrub|clear)\s*(.*)", re.IGNORECASE),
    ]
    _DEEP_HINTS = re.compile(r"(深层|深度|全面|彻底|all|deep|thorough)", re.IGNORECASE)
    _DUP_HINTS = re.compile(r"(重复|duplicate|重复文件)", re.IGNORECASE)
    _OLD_HINTS = re.compile(r"(旧文件|老文件|很久没用|old files|stale)", re.IGNORECASE)

    def parse(self, user_query: str) -> ScanConfig:
        cfg = ScanConfig(user_query=user_query)
        cfg = self._extract_drives(user_query, cfg)
        cfg = self._extract_keeps(user_query, cfg)
        cfg = self._infer_mode(user_query, cfg)
        cfg = self._infer_features(user_query, cfg)
        return cfg

    def _extract_drives(self, q: str, cfg: ScanConfig) -> ScanConfig:
        for pat in self._DRIVE_PATTERNS:
            for m in pat.finditer(q):
                raw = m.group(1).upper().rstrip(":\\").rstrip("/")
                if len(raw) == 1 and raw.isalpha():
                    cfg.target_paths.append(Path(f"{raw}:\\"))
        if not cfg.target_paths:
            cfg.target_paths = [Path(p) for p in ("C:\\", "D:\\", "E:\\")]
        return cfg

    def _extract_keeps(self, q: str, cfg: ScanConfig) -> ScanConfig:
        for pat in self._KEEP_HINTS:
            for m in pat.finditer(q):
                kept = m.group(2).strip()
                if not kept:
                    continue
                patterns = self._entity_to_path_patterns(kept)
                cfg.exclude_paths.extend(Path(p) for p in patterns)
        return cfg

    def _entity_to_path_patterns(self, entity: str) -> list[str]:
        e = entity.lower().strip()
        KNOWN = {
            "原神": ["*原神*", "*GenshinImpact*", "*yuanshen*", "*Genshin*"],
            "微信": ["*WeChat*", "*xwechat*", "*Tencent*WeChat*"],
            "qq": ["*QQ*", "*Tencent*QQ*"],
            "steam": ["*Steam*", "*steamapps*"],
            "vmware": ["*VMware*", "*Virtual Machines*"],
            "kali": ["*kali*", "*Kali*"],
            "ubuntu": ["*ubuntu*", "*Ubuntu*"],
            "代码": ["*code*", "*src*", "*project*", "*workspace*"],
            "照片": ["*Pictures*", "*Photos*", "*photo*", "*DCIM*"],
            "视频": ["*Videos*", "*Movies*", "*video*"],
            "文档": ["*Documents*", "*文档*"],
            "游戏": ["*game*", "*Game*", "*steamapps*"],
            "idea": ["*IntelliJ*", "*IDEA*", "*JetBrains*"],
            "vscode": ["*Visual Studio Code*", "*vscode*", "*.vscode*"],
            "wsl": ["*WSL*", "*wsl*", "*ext4.vhdx*"],
            "docker": ["*Docker*", "*docker*"],
        }
        return KNOWN.get(e, [f"*{e}*"])

    def _infer_mode(self, q: str, cfg: ScanConfig) -> ScanConfig:
        if re.search(r"(真的删|确实删|我确认|--execute|确认清理)", q, re.IGNORECASE):
            cfg.deletion_mode = DeletionMode.HARD
        elif re.search(r"(试一下|看看|试运行|先看|预览)", q, re.IGNORECASE):
            cfg.deletion_mode = DeletionMode.DRY_RUN
        return cfg

    def _infer_features(self, q: str, cfg: ScanConfig) -> ScanConfig:
        if self._DEEP_HINTS.search(q):
            cfg.deep = True
            cfg.min_size_mb = 10  # lower threshold for deep scans
        if self._DUP_HINTS.search(q):
            cfg.include_duplicates = True
        if self._OLD_HINTS.search(q):
            cfg.include_old_files = True
        return cfg


# ===========================================================================
# 2. Cognitive Adapter — 3-level labeling
# ===========================================================================

@dataclass(frozen=True)
class _FingerprintRule:
    """Level-1 hard fingerprint: exact path substring or feature file match."""
    path_substring: str = ""
    feature_file: str = ""
    label: str = ""
    risk: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    suggested_action: str = "review"


class _LabelingLLM(Protocol):
    """Optional LLM interface for Level-2 inference."""
    def infer(self, summary: DirectorySummary) -> dict: ...


class CognitiveAdapter:
    """Three-level labeling: fingerprint → AI → fallback.

    Level 1: Hard fingerprint — path/extension/suffix exact match.
    Level 2: AI inference — send feature_files to LLM for context.
    Level 3: Fallback — "未知的大型应用数据".
    """

    # ---- Level 1 fingerprints ----------------------------------------

    _FINGERPRINTS: list[_FingerprintRule] = [
        # === Dev caches (safe to delete, auto-rebuild) ===
        _FingerprintRule(path_substring=r"\npm-cache", label="npm 依赖缓存",
                         risk="重装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\pip\cache", label="Python pip 缓存",
                         risk="重装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.cargo\registry", label="Rust Cargo 缓存",
                         risk="编译时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.gradle\caches", label="Gradle 构建缓存",
                         risk="编译时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.m2\repository", label="Maven 依赖缓存",
                         risk="编译时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.nuget\packages", label="NuGet 包缓存",
                         risk="编译时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\ms-playwright", label="Playwright 浏览器缓存",
                         risk="测试时自动下载", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Yarn\Cache", label="Yarn 依赖缓存",
                         risk="安装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\pnpm\store", label="pnpm 依赖缓存",
                         risk="安装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.bun\install", label="Bun 包缓存",
                         risk="安装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.uv\cache", label="uv 包缓存",
                         risk="安装时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),

        # === IDE caches (safe to delete, rebuild on next open) ===
        _FingerprintRule(path_substring=r"\JetBrains", label="JetBrains IDE 缓存",
                         risk="重新索引即可恢复", risk_level=RiskLevel.LOW,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\VisualStudio", label="Visual Studio 缓存",
                         risk="重新生成即可恢复", risk_level=RiskLevel.LOW,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\AndroidStudio", label="Android Studio 缓存",
                         risk="重新索引即可恢复", risk_level=RiskLevel.LOW,
                         suggested_action="delete_safely"),

        # === Project dependencies (review before delete) ===
        _FingerprintRule(path_substring=r"\node_modules", label="Node.js 项目依赖包",
                         risk="重装时 npm install 即可恢复", risk_level=RiskLevel.LOW,
                         suggested_action="review"),
        _FingerprintRule(path_substring=r"\__pycache__", label="Python 字节码缓存",
                         risk="运行时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\.next", label="Next.js 构建缓存",
                         risk="构建时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\target\release", label="Rust 构建产物",
                         risk="编译时自动重建", risk_level=RiskLevel.LOW,
                         suggested_action="review"),
        _FingerprintRule(path_substring=r"\target\debug", label="Rust 调试构建",
                         risk="编译时自动重建", risk_level=RiskLevel.LOW,
                         suggested_action="review"),

        # === Browser caches (safe to delete) ===
        _FingerprintRule(path_substring=r"\Chrome\User Data\Default\Cache",
                         label="Chrome 浏览器缓存", risk="不影响书签密码",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Chrome\User Data\Default\Code Cache",
                         label="Chrome 代码缓存", risk="不影响书签密码",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Edge\User Data\Default\Cache",
                         label="Edge 浏览器缓存", risk="不影响书签密码",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Brave-Browser\User Data\Default\Cache",
                         label="Brave 浏览器缓存", risk="不影响书签密码",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Firefox\Profiles", label="Firefox 浏览器数据",
                         risk="包含书签、密码、扩展", risk_level=RiskLevel.HIGH,
                         suggested_action="ask_user"),

        # === Browser profiles (review, contains user data) ===
        _FingerprintRule(path_substring=r"\Google\Chrome\User Data",
                         label="Chrome 浏览器数据", risk="包含书签、密码、扩展",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\Microsoft\Edge\User Data",
                         label="Edge 浏览器数据", risk="包含书签、密码、扩展",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\BraveSoftware\Brave-Browser\User Data",
                         label="Brave 浏览器数据", risk="包含书签、密码、扩展",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),

        # === Chat apps ===
        _FingerprintRule(path_substring=r"\xwechat_files\FileStorage\Cache",
                         label="微信文件缓存", risk="不影响聊天记录",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\xwechat_files\FileStorage\Image",
                         label="微信图片缓存", risk="不影响核心聊天记录",
                         risk_level=RiskLevel.LOW, suggested_action="review"),
        _FingerprintRule(path_substring=r"\xwechat_files",
                         label="微信聊天数据（含你的聊天记录）",
                         risk="聊天记录、表情包、重要文件都在里面",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\Tencent\QQ",
                         label="QQ 聊天数据", risk="聊天记录会丢失",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\Discord\Cache",
                         label="Discord 缓存", risk="不影响账号",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Slack\Cache",
                         label="Slack 缓存", risk="不影响消息",
                         risk_level=RiskLevel.NONE, suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Telegram Desktop",
                         label="Telegram 数据", risk="聊天记录和文件",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),

        # === VMs ===
        _FingerprintRule(feature_file="*.vmdk", label="VMware 虚拟机磁盘文件",
                         risk="删了虚拟机就打不开了",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(feature_file="*.vmx", label="VMware 虚拟机配置",
                         risk="虚拟机配置会丢失",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(feature_file="*.vmsn", label="VMware 虚拟机快照",
                         risk="快照无法恢复",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),
        _FingerprintRule(feature_file="ext4.vhdx", label="WSL Linux 虚拟磁盘",
                         risk="WSL 系统和数据全部丢失",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),

        # === Installers ===
        _FingerprintRule(feature_file="setup.exe", label="Windows 安装程序",
                         risk="可能还要用", risk_level=RiskLevel.MEDIUM,
                         suggested_action="review"),
        _FingerprintRule(feature_file="*.iso", label="光盘镜像文件",
                         risk="可能还要安装用", risk_level=RiskLevel.MEDIUM,
                         suggested_action="review"),
        _FingerprintRule(feature_file="*.dmg", label="macOS 安装镜像",
                         risk="可能还要安装用", risk_level=RiskLevel.MEDIUM,
                         suggested_action="review"),

        # === System temp (safe to delete) ===
        _FingerprintRule(path_substring=r"\CrashDumps", label="系统崩溃转储",
                         risk="已无用，安全删除", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Windows\Temp", label="Windows 临时文件",
                         risk="已无用，安全删除", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\AppData\Local\Temp", label="应用程序临时文件",
                         risk="已无用，安全删除", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Windows\SoftwareDistribution\Download",
                         label="Windows 更新缓存", risk="更新完成后可清理",
                         risk_level=RiskLevel.LOW, suggested_action="review"),
        _FingerprintRule(path_substring=r"\Windows\Logs", label="Windows 日志",
                         risk="已无用，安全删除", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\WER\Report", label="错误报告",
                         risk="已无用，安全删除", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),

        # === Cloud sync ===
        _FingerprintRule(path_substring=r"\OneDrive\Cache", label="OneDrive 缓存",
                         risk="不影响云端文件", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\OneDrive", label="OneDrive 同步数据",
                         risk="本地文件可能未同步到云端",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),

        # === Games ===
        _FingerprintRule(path_substring=r"\steamapps\common", label="Steam 游戏",
                         risk="卸载后需重新下载", risk_level=RiskLevel.HIGH,
                         suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\Steam\shadercache", label="Steam 着色器缓存",
                         risk="游戏运行时自动重建", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Steam\htmlcache", label="Steam 浏览器缓存",
                         risk="不影响游戏", risk_level=RiskLevel.NONE,
                         suggested_action="delete_safely"),
        _FingerprintRule(path_substring=r"\Epic Games", label="Epic 游戏数据",
                         risk="卸载后需重新下载", risk_level=RiskLevel.HIGH,
                         suggested_action="ask_user"),

        # === Docker ===
        _FingerprintRule(path_substring=r"\Docker\desktop", label="Docker 桌面数据",
                         risk="容器和镜像会丢失", risk_level=RiskLevel.HIGH,
                         suggested_action="ask_user"),
        _FingerprintRule(path_substring=r"\wsl\docker-desktop", label="Docker WSL 数据",
                         risk="容器和镜像会丢失", risk_level=RiskLevel.HIGH,
                         suggested_action="ask_user"),

        # === WSL ===
        _FingerprintRule(path_substring=r"\Packages\CanonicalGroupLimited.Ubuntu",
                         label="Ubuntu WSL 应用数据", risk="WSL 系统和数据全部丢失",
                         risk_level=RiskLevel.HIGH, suggested_action="ask_user"),

        # === Miscellaneous ===
        _FingerprintRule(path_substring=r"\.cache", label="应用缓存",
                         risk="通常可安全删除", risk_level=RiskLevel.LOW,
                         suggested_action="review"),
        _FingerprintRule(path_substring=r"\Cache", label="应用缓存",
                         risk="通常可安全删除", risk_level=RiskLevel.LOW,
                         suggested_action="review"),
    ]

    def __init__(self, llm: _LabelingLLM | None = None) -> None:
        self._llm = llm

    def label(self, summary: DirectorySummary) -> CleanEntry:
        """Route through 3 levels and return a fully labeled CleanEntry."""
        # Level 1: try hard fingerprint first
        label = self._level1_fingerprint(summary)
        if label is not None:
            return self._build_entry(summary, label)

        # Level 2: try AI inference (if LLM available and enough signal)
        if self._llm is not None and summary.feature_files:
            label = self._level2_ai(summary)
            if label is not None:
                return self._build_entry(summary, label)

        # Level 3: fallback
        label = self._level3_fallback(summary)
        return self._build_entry(summary, label)

    # ---- Level 1: Hard fingerprint ------------------------------------

    def _level1_fingerprint(self, s: DirectorySummary) -> CognitiveLabel | None:
        path_str = str(s.path)

        # Check feature_files against known patterns
        for rule in self._FINGERPRINTS:
            if rule.path_substring and rule.path_substring.lower() in path_str.lower():
                return CognitiveLabel(
                    source=LabelSource.LEVEL_1_FINGERPRINT,
                    human_readable_label=rule.label,
                    human_readable_risk=rule.risk,
                    confidence=0.95,
                    technical_name=s.path.name,
                    technical_path=path_str,
                    suggested_action=rule.suggested_action,
                )

            if rule.feature_file:
                for ff in s.feature_files:
                    if _glob_match(ff, rule.feature_file):
                        return CognitiveLabel(
                            source=LabelSource.LEVEL_1_FINGERPRINT,
                            human_readable_label=rule.label,
                            human_readable_risk=rule.risk,
                            confidence=0.9,
                            technical_name=ff,
                            technical_path=path_str,
                            suggested_action=rule.suggested_action,
                        )

        # Check feature_dirs for known patterns
        KNOWN_DIRS = {
            "node_modules": ("Node.js 项目依赖包", "重装时 npm install 即可恢复"),
            ".git": ("Git 版本历史", "删除后无法查看提交记录"),
            "__pycache__": ("Python 字节码缓存", "运行时自动重建"),
            ".venv": ("Python 虚拟环境", "可重新创建"),
            "venv": ("Python 虚拟环境", "可重新创建"),
            ".gradle": ("Gradle 缓存", "编译时自动重建"),
            ".idea": ("IntelliJ IDEA 配置", "重新导入项目即可"),
            ".vscode": ("VS Code 配置", "重新打开项目即可"),
            "build": ("构建产物", "编译时自动重建"),
            "dist": ("分发产物", "构建时自动重建"),
            "target": ("构建产物", "编译时自动重建"),
            ".next": ("Next.js 缓存", "构建时自动重建"),
        }
        for fd in s.feature_dirs:
            lower_fd = fd.lower()
            for key, (label, risk) in KNOWN_DIRS.items():
                if key.lower() == lower_fd:
                    return CognitiveLabel(
                        source=LabelSource.LEVEL_1_FINGERPRINT,
                        human_readable_label=label,
                        human_readable_risk=risk,
                        confidence=0.85,
                        technical_name=fd,
                        technical_path=path_str,
                        suggested_action="review",
                    )

        return None

    # ---- Level 2: AI inference ----------------------------------------

    def _level2_ai(self, s: DirectorySummary) -> CognitiveLabel | None:
        if self._llm is None:
            return None
        try:
            result = self._llm.infer(s)
            return CognitiveLabel(
                source=LabelSource.LEVEL_2_AI_INFERENCE,
                human_readable_label=result.get("label", "未知应用数据"),
                human_readable_risk=result.get("risk", "建议先确认"),
                confidence=float(result.get("confidence", 0.6)),
                technical_name=s.path.name,
                technical_path=str(s.path),
                ai_reasoning=result.get("reasoning", ""),
                suggested_action=result.get("action", "review"),
            )
        except Exception:
            return None

    # ---- Level 3: Fallback --------------------------------------------

    def _level3_fallback(self, s: DirectorySummary) -> CognitiveLabel:
        if s.total_bytes >= 1 * 1024**3:
            size_desc = "很大的"
        elif s.total_bytes >= 100 * 1024**2:
            size_desc = "中等大小的"
        else:
            size_desc = "较小的"
        parts = s.path.parts
        last = parts[-1] if parts else "未知"
        # Strip ALL technical suffixes — user never sees ".tmp", ".dll", etc.
        # In Level-3 fallback, we have no idea what the file IS, so the
        # extension is always noise. Just use the stem.
        stem = Path(last).stem
        if not stem or stem.startswith("."):
            stem = last.split(".")[0] if "." in last else last
        return CognitiveLabel(
            source=LabelSource.LEVEL_3_FALLBACK,
            human_readable_label=f"{size_desc}应用数据：{stem}",
            human_readable_risk="系统无法识别这是什么，先别动",
            confidence=0.3,
            technical_name=last,
            technical_path=str(s.path),
            ai_reasoning=None,
            suggested_action="review",
        )

    # ---- Helper -------------------------------------------------------

    def _build_entry(self, s: DirectorySummary, label: CognitiveLabel) -> CleanEntry:
        return CleanEntry(
            id=_entry_id(s.path),
            summary=s,
            label=label,
            risk_level=self._label_to_risk(label),
        )

    @staticmethod
    def _label_to_risk(label: CognitiveLabel) -> RiskLevel:
        action = label.suggested_action
        if action == "delete_safely":
            return RiskLevel.NONE
        if action == "review":
            return RiskLevel.MEDIUM
        if action in ("keep", "ask_user"):
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM


# ===========================================================================
# 3. AIBrain — orchestrates the two
# ===========================================================================

class AIBrain:
    """Top-level entry for natural-language driven scans.

    Usage:
        brain = AIBrain()
        cfg = brain.parse_intent("清理C盘，保留原神")
        summaries = scanner.scan(cfg)
        entries = brain.label_all(summaries)
    """

    def __init__(self, llm: _LabelingLLM | None = None) -> None:
        self.intent_parser = IntentParser()
        self.cognitive = CognitiveAdapter(llm=llm)

    def parse_intent(self, user_query: str) -> ScanConfig:
        return self.intent_parser.parse(user_query)

    def label_all(self, summaries: list[DirectorySummary]) -> list[CleanEntry]:
        return [self.cognitive.label(s) for s in summaries]

    def label_one(self, summary: DirectorySummary) -> CleanEntry:
        return self.cognitive.label(summary)


# ===========================================================================
# Helpers
# ===========================================================================

def _entry_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]


def _glob_match(filename: str, pattern: str) -> bool:
    """Simple glob match: *.vmdk matches Kali.vmdk."""
    return fnmatch.fnmatch(filename.lower(), pattern.lower())


# ===========================================================================
# Demo
# ===========================================================================

def _demo() -> list[CleanEntry]:
    """Demo: D:\\VMware\\Kali.vmdk and C:\\Users\\x\\Downloads\\setup.exe.

    Path 1: D:\\VMware\\Kali.vmdk
      → label: "VMware 虚拟机磁盘文件"
      → risk: "删了虚拟机就打不开了"
      → User sees: "— VMware 虚拟机磁盘文件 (14.0GB)"
                     "  ⚠ 删了虚拟机就打不开了"

    Path 2: C:\\Users\\x\\Downloads\\setup.exe
      → label: "Windows 安装程序"
      → risk: "可能还要用"
      → User sees: "— Windows 安装程序 (50.0MB)"
                     "  ⚠ 可能还要用"
    """
    s1 = DirectorySummary(
        path=Path(r"D:\VMware\Kali.vmdk"),
        total_bytes=14 * 1024**3,
        file_count=1,
        feature_files=["Kali.vmdk"],
        has_lock_files=False,
    )
    s2 = DirectorySummary(
        path=Path(r"C:\Users\x\Downloads\setup.exe"),
        total_bytes=50 * 1024**2,
        file_count=1,
        feature_files=["setup.exe"],
        has_lock_files=False,
    )
    adapter = CognitiveAdapter()
    return [adapter.label(s1), adapter.label(s2)]


if __name__ == "__main__":
    for entry in _demo():
        print(entry.user_facing_prompt)
        print(f"  风险等级: {entry.risk_level}")
        print(f"  技术路径: {entry.label.technical_path}")
        print(f"  标签来源: {entry.label.source}")
        print()
