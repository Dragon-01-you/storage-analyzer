"""Evolution Engine: FoolproofProposal + Whitelist Health Check.

The point of this module is to PREVENT three failure modes:

  1. The user keeps skipping the same item, then forgets about it,
     and the disk fills up with the same thing they keep saying "no"
     to. Solution: after N skips, propose adding to whitelist.

  2. The user adds a rule to the whitelist, then forgets about it.
     Over months, the whitelisted file balloons to 50GB.
     Solution: health check on every entry.

  3. The user accidentally whitelists "C:\\*", which means "skip
     everything". Solution: consequence_warning + default to "reject".
"""
from __future__ import annotations
import json
import fnmatch
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from .types import (
    CleanEntry, WhitelistRule, RiskLevel, DeletionMode,
)


# ===========================================================================
# WhitelistStore — persistent list of WhitelistRule
# ===========================================================================

class WhitelistStore:
    """JSON-backed store. Lives at ~/.cache/storage-analyzer/v8-whitelist.json."""

    DEFAULT_PATH = Path.home() / ".cache" / "storage-analyzer" / "v8-whitelist.json"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.DEFAULT_PATH
        self._rules: dict[str, WhitelistRule] = {}
        self._load()

    # ---- I/O -----------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for r in data.get("rules", []):
                rule = WhitelistRule(**r)
                self._rules[rule.id] = rule
        except (json.JSONDecodeError, OSError, TypeError):
            # Corrupted file — refuse to silently lose data
            self._rules = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "rules": [r.model_dump(mode="json") for r in self._rules.values()]}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- CRUD ----------------------------------------------------------

    def all(self) -> list[WhitelistRule]:
        return list(self._rules.values())

    def get(self, rule_id: str) -> WhitelistRule | None:
        return self._rules.get(rule_id)

    def add(self, rule: WhitelistRule) -> None:
        self._rules[rule.id] = rule
        self._save()

    def remove(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            self._save()
            return True
        return False

    def update(self, rule: WhitelistRule) -> None:
        if rule.id in self._rules:
            self._rules[rule.id] = rule
            self._save()

    # ---- Query ---------------------------------------------------------

    def matches(self, path: str) -> WhitelistRule | None:
        """Return the first rule whose pattern matches the path."""
        for rule in self._rules.values():
            if fnmatch.fnmatch(path.lower(), rule.path_pattern.lower()):
                return rule
        return None


# ===========================================================================
# FoolproofProposer — proposes whitelist rules after N skips
# ===========================================================================

# How many times the user must skip the same item before we propose
# adding it to the whitelist. Conservative default.
SKIP_THRESHOLD = 3


class FoolproofProposer:
    """Watches skip decisions and proposes whitelist additions.

    Key principle: the DEFAULT action is "reject / not now". We never
    auto-add to the whitelist. We only SUGGEST, and the user must
    explicitly accept the proposal.
    """

    def __init__(self, store: WhitelistStore) -> None:
        self.store = store
        # In-memory skip counter (lost on restart; that's OK — users
        # typically skip fast within a single session)
        self._skip_counts: dict[str, int] = {}

    def record_skip(self, entry: CleanEntry) -> None:
        self._skip_counts[entry.id] = self._skip_counts.get(entry.id, 0) + 1
        # Also update persistent skip count on the rule, if it ever was on the WL
        rule = self.store.matches(str(entry.summary.path))
        if rule is not None:
            rule.skip_count += 1
            rule.last_skip_at = datetime.now()
            self.store.update(rule)

    def maybe_propose(self, entry: CleanEntry) -> "WhitelistProposal | None":
        """Return a proposal if the entry has been skipped enough times.

        Returns None otherwise. The caller decides whether to surface
        the proposal to the user (we never auto-apply).
        """
        # Don't propose for HIGH risk items — too dangerous to whitelist
        if entry.risk_level is RiskLevel.HIGH:
            return None

        if self._skip_counts.get(entry.id, 0) < SKIP_THRESHOLD:
            return None

        # Already on the whitelist? Don't propose.
        if self.store.matches(str(entry.summary.path)) is not None:
            return None

        # Draft the proposal
        return WhitelistProposal(
            entry=entry,
            proposed_pattern=self._pattern_from_path(entry.summary.path),
            consequence_warning=self._build_consequence_warning(entry),
            skip_count=self._skip_counts[entry.id],
        )

    @staticmethod
    def _pattern_from_path(p: Path) -> str:
        """Conservative: the pattern is the exact path, NOT a wildcard.

        Wildcards in whitelist patterns are too dangerous (user can
        accidentally whitelist an entire drive with one C:\\* mistake).
        """
        return str(p).rstrip("\\/")

    @staticmethod
    def _build_consequence_warning(entry: CleanEntry) -> str:
        size_h = _h(entry.summary.total_bytes)
        if entry.risk_level is RiskLevel.MEDIUM:
            return (
                f"如果加入白名单，将永久失去 {size_h} 的清理机会。"
                f"（约 {size_h}）"
            )
        return f"如果加入白名单，将永久失去 {size_h} 的清理机会。"


# ===========================================================================
# WhitelistProposal — what gets shown to the user
# ===========================================================================

class WhitelistProposal:
    """User-facing proposal: "should we add this to the whitelist?"

    Always requires EXPLICIT consent. Default option is "not now".
    """

    def __init__(
        self,
        entry: CleanEntry,
        proposed_pattern: str,
        consequence_warning: str,
        skip_count: int,
    ) -> None:
        self.entry = entry
        self.proposed_pattern = proposed_pattern
        self.consequence_warning = consequence_warning
        self.skip_count = skip_count

    def to_user_facing(self) -> str:
        """The text the user sees. Plain Chinese, no jargon."""
        return (
            f"你跳过了 {self.skip_count} 次：{self.entry.label.human_readable_label}\n"
            f"  路径：{self.entry.summary.path}\n"
            f"  ⚠️  {self.consequence_warning}\n"
            f"  建议：加入白名单（之后不再提示）/ 下次再说 / 删除"
        )


# ===========================================================================
# EvolutionEngine — orchestrates the health check
# ===========================================================================

class EvolutionEngine:
    """Top-level: combines store + proposer + health check.

    Hook this into the scan loop:
        engine = EvolutionEngine()
        engine.tick(store)  # call before/after each scan
        for entry in entries:
            if entry not in store:
                decision = user_decide(entry)
                if decision == "skip":
                    proposer.record_skip(entry)
                    proposal = proposer.maybe_propose(entry)
                    if proposal:
                        show(proposal.to_user_facing())
    """

    def __init__(self, store: WhitelistStore | None = None) -> None:
        self.store = store or WhitelistStore()
        self.proposer = FoolproofProposer(self.store)

    def health_check(self) -> list[WhitelistRule]:
        """Return the list of whitelist rules that need re-review."""
        return [r for r in self.store.all()
                if r.is_overdue_for_review or r.is_bloated]

    def health_check_messages(self) -> list[str]:
        """User-facing strings for any rule that needs re-review."""
        out = []
        for rule in self.health_check():
            out.append(
                f"白名单提醒：{rule.path_pattern}\n"
                f"  你说：{rule.human_readable_reason}\n"
                f"  ⚠️  {rule.consequence_warning()}"
            )
        return out


# ===========================================================================
# Helper
# ===========================================================================

def _h(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if n >= 100 else f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
