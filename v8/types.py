"""Pydantic v2 data contracts.

Every cross-module argument and return value uses one of these types.
Plain dicts are forbidden at module boundaries — typing beats guessing.

Key principle: a CleanEntry's `human_readable_label` is the ONLY string
that ever reaches the user. Internal technical names stay in
`technical_name` for logs and audit.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    """How dangerous deletion is. Drives UI color, default action, and
    whether the user even sees this entry (high-risk ones always ask)."""
    NONE = "none"           # safe to one-click delete (Temp, browser cache)
    LOW = "low"             # probably safe (browser profile, dev cache)
    MEDIUM = "medium"       # review recommended (IDE cache, Docker)
    HIGH = "high"           # always ask (browser history, system state)


class SafetyTier(str, Enum):
    """Hard-coded deletion routing. Cannot be overridden by config or AI."""
    RECYCLE_BIN = "recycle_bin"     # small files, recoverable
    QUARANTINE = "quarantine"       # large files, time-limited holding
    WIPE = "wipe"                   # only with explicit consent + audit


class DeletionMode(str, Enum):
    DRY_RUN = "dry_run"     # never deletes, only reports
    SOFT = "soft"           # recycle bin / quarantine
    HARD = "hard"           # actually deletes (after all checks)


class LabelSource(str, Enum):
    """Which level of the CognitiveAdapter produced this label."""
    LEVEL_1_FINGERPRINT = "l1"     # exact match (path / suffix / known app)
    LEVEL_2_AI_INFERENCE = "l2"    # LLM inferred from feature files
    LEVEL_3_FALLBACK = "l3"        # "unknown large app data"


# ---------------------------------------------------------------------------
# Intent parsing output
# ---------------------------------------------------------------------------

class ScanConfig(BaseModel):
    """The structured output of IntentParser.

    Drives the entire downstream pipeline. Anything not in ScanConfig
    is not scanned (defense against runaway scans).
    """
    model_config = ConfigDict(extra="forbid")

    # Free-text from the user (kept for audit, never used as code)
    user_query: str = ""

    # Scope
    target_paths: list[Path] = Field(default_factory=list)
    exclude_paths: list[Path] = Field(default_factory=list)

    # Mode
    deep: bool = True                # include system / dev caches
    include_duplicates: bool = False
    include_old_files: bool = False  # files not touched in N days

    # Heuristics
    min_size_mb: int = Field(default=50, ge=1, le=10_000)
    old_threshold_days: int = Field(default=180, ge=30, le=3650)

    # Safety
    deletion_mode: DeletionMode = DeletionMode.DRY_RUN
    require_explicit_consent_for: list[RiskLevel] = Field(
        default_factory=lambda: [RiskLevel.MEDIUM, RiskLevel.HIGH]
    )

    # Cognitive options
    enable_ai_judge: bool = False
    ai_judge_budget: int = Field(default=20, ge=0, le=500)

    @field_validator("exclude_paths")
    @classmethod
    def _exclude_must_not_be_empty(cls, v: list[Path]) -> list[Path]:
        # Excluding "/" or "C:\" means "delete everything" — reject
        for p in v:
            if str(p) in ("/", "\\", "C:\\", "C:/", ""):
                raise ValueError(f"Refusing to exclude root path: {p!r}")
        return v

    @model_validator(mode="after")
    def _hard_mode_requires_consent(self) -> "ScanConfig":
        if self.deletion_mode is DeletionMode.HARD:
            if not self.require_explicit_consent_for:
                raise ValueError(
                    "HARD deletion mode MUST require explicit consent for "
                    "MEDIUM and HIGH risk items — refuse to start"
                )
        return self


# ---------------------------------------------------------------------------
# Funnel scanner output (compressed summaries, never raw file lists)
# ---------------------------------------------------------------------------

class DirectorySummary(BaseModel):
    """Compressed representation of a directory.

    FunnelScanner never returns full file trees to higher layers.
    The summary is enough to make a decision; the raw tree is only
    touched by the actual deletion code (Safeguard) at the end.

    The 'feature_files' field is the ONLY rich signal that survives
    compression — it's what the CognitiveAdapter's Level-2 uses.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    total_bytes: int = 0
    file_count: int = 0
    last_access: datetime | None = None
    last_modified: datetime | None = None

    # What makes this directory "look like" something (package.json,
    # .vmx, *.vmdk, etc.). At most ~20 entries to keep the AI input
    # bounded. NEVER the full file list.
    feature_files: list[str] = Field(default_factory=list, max_length=20)
    feature_dirs: list[str] = Field(default_factory=list, max_length=10)

    # Cheap heuristics
    has_lock_files: bool = False        # VM is running, etc.
    contains_user_data: bool = False    # photos, documents, code

    @property
    def total_mb(self) -> float:
        return self.total_bytes / 1024 / 1024

    @property
    def age_days(self) -> int | None:
        if self.last_access is None:
            return None
        return (datetime.now() - self.last_access).days


# ---------------------------------------------------------------------------
# CleanEntry: the user-facing object after CognitiveAdapter labels it
# ---------------------------------------------------------------------------

class CognitiveLabel(BaseModel):
    """The output of CognitiveAdapter's three-level labeling.

    This is the contract between AI Brain and the rest of the world.
    The user never sees technical_name — they see human_readable_label.
    """
    source: LabelSource
    human_readable_label: str           # "微信聊天图片缓存" not "xwechat_files/Image/Storage"
    human_readable_risk: str           # "可能被清理软件误判，建议先看一眼" not "med"
    confidence: float = Field(ge=0.0, le=1.0)

    # The technical truth, kept for audit
    technical_name: str = ""
    technical_path: str = ""

    # LLM-only: what the AI thought (Level 2)
    ai_reasoning: str | None = None

    # Suggested action (one of: "delete_safely", "review", "keep", "ask_user")
    suggested_action: Literal["delete_safely", "review", "keep", "ask_user"] = "review"


class CleanEntry(BaseModel):
    """A single cleanup candidate, labeled and ready for the user.

    Built from a DirectorySummary by passing it through CognitiveAdapter.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str                             # short stable id (hash of path)
    summary: DirectorySummary
    label: CognitiveLabel

    # Computed fields (set by EvolutionEngine, defaults OK)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    safety_tier: SafetyTier = SafetyTier.RECYCLE_BIN
    skip_count: int = 0                 # how many times user skipped this
    last_user_decision: datetime | None = None

    # If on whitelist, no cognitive work needed
    whitelisted: bool = False

    @property
    def human_summary(self) -> str:
        """The single line of text the user actually reads."""
        size_h = _human_bytes(self.summary.total_bytes)
        return f"{self.label.human_readable_label} ({size_h})"

    @property
    def user_facing_prompt(self) -> str:
        """Multi-line text. Includes the consequence_warning space."""
        risk_line = ""
        if self.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            risk_line = f"\n  ⚠️  {self.label.human_readable_risk}"
        return f"• {self.human_summary}{risk_line}"


# ---------------------------------------------------------------------------
# Whitelist (Evolution Engine)
# ---------------------------------------------------------------------------

class WhitelistRule(BaseModel):
    """A user-acknowledged rule: "don't ever ask about this again".

    The health-check fields (`total_size_bytes`, `last_reviewed_at`) are
    what prevent the whitelist from becoming a garbage trap. If the file
    under a whitelist entry has ballooned past the threshold, the user
    gets a "still safe?" prompt again.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    path_pattern: str                   # glob: "C:\\Users\\*\\Documents\\重要工作"
    human_readable_reason: str          # "我工作用的设计稿都在这里"
    created_at: datetime
    last_reviewed_at: datetime

    # The size AT THE TIME OF WHITELISTING (for "did this balloon?" check)
    baseline_size_bytes: int

    # Current observed size (updated by periodic scan)
    current_size_bytes: int = 0
    last_size_check: datetime | None = None

    # Counters that trigger health-check
    skip_count: int = 0                 # how many times user skipped
    last_skip_at: datetime | None = None

    @property
    def is_overdue_for_review(self) -> bool:
        """Health check 1: not reviewed in 30 days."""
        return (datetime.now() - self.last_reviewed_at) > timedelta(days=30)

    @property
    def is_bloated(self) -> bool:
        """Health check 2: grew past 5GB or 2x the baseline."""
        if self.current_size_bytes > 5 * 1024**3:
            return True
        if self.baseline_size_bytes > 0 and \
           self.current_size_bytes > 2 * self.baseline_size_bytes:
            return True
        return False

    def days_since_review(self) -> int:
        return (datetime.now() - self.last_reviewed_at).days

    def consequence_warning(self) -> str:
        """Shown when re-prompting. Forces the user to think."""
        if self.is_bloated:
            growth = self.current_size_bytes - self.baseline_size_bytes
            return (
                f"这条白名单从你上次确认到现在涨了 {(_human_bytes(growth))}。"
                f"如果继续保留，将永久失去这 {_human_bytes(self.current_size_bytes)} 的清理机会。"
            )
        return f"这条白名单已经 {self.days_since_review()} 天没重新审视过了。"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if n >= 100 else f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
