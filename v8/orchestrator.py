"""v8 Orchestrator: wires ALL modules into a single pipeline.

Modules:
  AI Brain + Engine Core + Evolution + Safeguard + ScanCache + Audit + History

This is the ONLY place where all modules are wired together.
Each module is independently testable; the orchestrator just coordinates.

Usage:
    from v8 import Orchestrator

    orch = Orchestrator()
    result = orch.run(
        ScanConfig(target_paths=[Path("C:\\")]),
        user_decision=lambda e: "approve" if e.risk_level == RiskLevel.NONE else "skip"
    )
    print(result.summary())
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .types import (
    ScanConfig, CleanEntry, DirectorySummary,
    DeletionMode, RiskLevel, SafetyTier,
)
from .ai_brain import AIBrain
from .engine_core import FunnelScanner
from .evolution import EvolutionEngine
from .safeguard import SafeDeleter, ProtectedPaths, ProtectedPathError
from .platform_paths import PlatformPaths
from .scan_cache import ScanCache
from .audit import AuditLogger
from .history import HistoryStore, Forecaster, take_all_snapshots, DiskSnapshot


log = logging.getLogger("v8.orchestrator")


@dataclass
class OrchestratorResult:
    """Complete result of a single scan-and-clean cycle."""
    config: ScanConfig
    summaries: list[DirectorySummary] = field(default_factory=list)
    entries: list[CleanEntry] = field(default_factory=list)
    approved: list[CleanEntry] = field(default_factory=list)
    skipped: list[CleanEntry] = field(default_factory=list)
    whitelist_health: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    bytes_freed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    scan_duration_s: float = 0
    label_duration_s: float = 0
    delete_duration_s: float = 0

    @property
    def total_found_bytes(self) -> int:
        return sum(e.summary.total_bytes for e in self.entries)

    @property
    def total_approved_bytes(self) -> int:
        return sum(e.summary.total_bytes for e in self.approved)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Scan: {len(self.summaries)} dirs, {len(self.entries)} candidates",
            f"  cache: {self.cache_hits} hits / {self.cache_misses} misses",
            f"  scan: {self.scan_duration_s:.1f}s, label: {self.label_duration_s:.1f}s",
            f"  approved: {len(self.approved)} ({_h(self.total_approved_bytes)})",
            f"  skipped: {len(self.skipped)}",
            f"  freed: {_h(self.bytes_freed)}",
        ]
        if self.errors:
            lines.append(f"  errors: {len(self.errors)}")
        return "\n".join(lines)


class Orchestrator:
    """End-to-end pipeline with all v8 modules integrated.

    The orchestrator is INTENTIONALLY thin — it doesn't make decisions.
    The four core modules are the decision makers.
    """

    def __init__(self, brain: AIBrain | None = None) -> None:
        self.brain = brain or AIBrain()
        self.evolution = EvolutionEngine()
        self.protected = ProtectedPaths()
        self.deleter = SafeDeleter(self.protected)
        self.audit = AuditLogger()
        self.history = HistoryStore()
        self.forecaster = Forecaster()

    def run(
        self,
        config: ScanConfig,
        user_decision: Callable[[CleanEntry], str] | None = None,
        use_cache: bool = True,
        record_history: bool = True,
    ) -> OrchestratorResult:
        """Run a full scan cycle.

        user_decision: callback returning one of {"approve", "skip", "whitelist"}.
                       If None, auto-approve NONE risk, skip everything else.
        use_cache: if True, check ScanCache before re-scanning dirs.
        record_history: if True, record disk snapshot to history.
        """
        result = OrchestratorResult(config=config)

        # --- Pre-scan: snapshot disk usage ---
        if record_history:
            drives = [str(p) for p in config.target_paths if Path(p).drive]
            snapshots = take_all_snapshots(drives)

        # --- Audit: scan started ---
        self.audit.log_scan_start(
            f"targets={[str(p) for p in config.target_paths]}, mode={config.deletion_mode.value}"
        )

        # --- Step 1: scan (with optional cache) ---
        t0 = time.time()
        scanner = FunnelScanner(config)
        if use_cache:
            result.summaries, result.cache_hits, result.cache_misses = \
                self._scan_with_cache(scanner)
        else:
            result.summaries = scanner.scan()
            result.cache_misses = len(result.summaries)
        result.scan_duration_s = time.time() - t0

        # --- Step 2: cognitive label ---
        t1 = time.time()
        result.entries = self.brain.label_all(result.summaries)
        result.label_duration_s = time.time() - t1

        # --- Step 3: whitelist health check ---
        result.whitelist_health = self.evolution.health_check_messages()
        for msg in result.whitelist_health:
            self.audit.log_whitelist_health("", msg)

        # --- Step 4: user decisions ---
        if user_decision is None:
            user_decision = self._safe_default_decision

        for entry in result.entries:
            # Skip whitelisted entries
            if self.evolution.store.matches(str(entry.summary.path)):
                continue

            # Always skip HIGH risk unless HARD mode
            if entry.risk_level is RiskLevel.HIGH and \
               config.deletion_mode is not DeletionMode.HARD:
                result.skipped.append(entry)
                continue

            decision = user_decision(entry)
            if decision == "whitelist":
                self._add_to_whitelist(entry, "用户主动添加")
                result.skipped.append(entry)
            elif decision == "skip":
                self.evolution.proposer.record_skip(entry)
                proposal = self.evolution.proposer.maybe_propose(entry)
                if proposal is not None:
                    log.info("PROPOSAL: %s", proposal.to_user_facing())
                result.skipped.append(entry)
            elif decision == "approve":
                result.approved.append(entry)
            else:
                result.errors.append(f"Unknown decision: {decision!r}")

        # --- Step 5: execute deletions ---
        t2 = time.time()
        if config.deletion_mode is not DeletionMode.DRY_RUN:
            for entry in result.approved:
                try:
                    ok, msg, freed = self.deleter.delete_entry(entry, config.deletion_mode)
                    if ok:
                        result.bytes_freed += freed
                    else:
                        result.errors.append(f"{entry.id}: {msg}")
                except ProtectedPathError as e:
                    result.errors.append(str(e))
                    self.audit.log_protected_block(str(entry.summary.path))
        result.delete_duration_s = time.time() - t2

        # --- Post-scan: record history ---
        self.audit.log_scan_end(
            len(result.entries), result.total_found_bytes, result.scan_duration_s
        )

        if record_history and snapshots:
            for s in snapshots:
                s.entry_count = len(result.entries)
                s.bytes_freed = result.bytes_freed
            self.history.record_many(snapshots)

        return result

    def _scan_with_cache(
        self, scanner: FunnelScanner
    ) -> tuple[list[DirectorySummary], int, int]:
        """Scan with cache. Returns (summaries, hits, misses)."""
        cache = ScanCache()
        # First get what scanner thinks should exist
        raw_summaries = scanner.scan()
        hits = 0
        misses = 0
        result = []

        for summary in raw_summaries:
            cached = cache.get(summary.path)
            if cached is not None:
                result.append(cached)
                hits += 1
            else:
                result.append(summary)
                cache.put(summary)
                misses += 1

        cache.close()
        return result, hits, misses

    def forecast(self, drives: list[str] | None = None) -> list[dict]:
        """Get disk forecast for specified drives."""
        if drives is None:
            drives = [str(p) for p in self.evolution.store.all()]
        results = []
        for drive in drives:
            snapshots = self.history.load(drive=drive, limit=90)
            fc = self.forecaster.forecast(snapshots)
            if fc:
                results.append({
                    "drive": fc.drive,
                    "days_until_full": fc.days_until_full,
                    "growth_per_day_bytes": fc.growth_per_day_bytes,
                    "current_free_bytes": fc.current_free_bytes,
                    "usage_pct": fc.current_usage_pct,
                    "is_urgent": fc.is_urgent,
                })
        return results

    @staticmethod
    def _safe_default_decision(entry: CleanEntry) -> str:
        """Conservative: approve only NONE risk, skip everything else."""
        if entry.risk_level is RiskLevel.NONE:
            return "approve"
        return "skip"

    def _add_to_whitelist(self, entry: CleanEntry, reason: str) -> None:
        from .types import WhitelistRule
        rule = WhitelistRule(
            id=entry.id,
            path_pattern=str(entry.summary.path),
            human_readable_reason=reason,
            created_at=datetime.now(),
            last_reviewed_at=datetime.now(),
            baseline_size_bytes=entry.summary.total_bytes,
            current_size_bytes=entry.summary.total_bytes,
            last_size_check=datetime.now(),
        )
        self.evolution.store.add(rule)
        self.audit.log_whitelist_add(entry, reason)


def _h(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if n >= 100 else f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
