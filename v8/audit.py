"""Structured JSON Lines audit logger.

Every deletion action is logged to ~/.cache/storage-analyzer/audit.jsonl.
Each entry is a single JSON line, containing:
  - timestamp, action, entry_id, path, size, risk, note
  - sha256 of the previous log entry (chain integrity)

This creates a tamper-evident chain: if someone edits a log line,
the chain hash breaks on the next entry.

For compliance and debugging. Never deletes audit logs.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .types import CleanEntry, RiskLevel, SafetyTier, DeletionMode


_AUDIT_DIR = Path.home() / ".cache" / "storage-analyzer"
_AUDIT_FILE = _AUDIT_DIR / "audit.jsonl"


class AuditLogger:
    """Append-only JSON Lines logger with chain integrity."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _AUDIT_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        """Read the last entry's chain_hash to resume the chain."""
        if not self.path.exists():
            return "genesis"
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return "genesis"
            last = json.loads(lines[-1])
            return last.get("chain_hash", "genesis")
        except (json.JSONDecodeError, OSError):
            return "genesis"

    def log_action(
        self,
        action: str,
        entry: CleanEntry | None,
        note: str,
        extra: dict | None = None,
    ) -> dict:
        """Append one audit entry. Returns the entry dict."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "ts": now,
            "action": action,
            "entry_id": entry.id if entry else "",
            "path": str(entry.summary.path) if entry else "",
            "size_bytes": entry.summary.total_bytes if entry else 0,
            "risk": entry.risk_level.value if entry else "",
            "safety_tier": entry.safety_tier.value if entry else "",
            "label": entry.label.human_readable_label if entry else "",
            "note": note,
            "prev_hash": self._last_hash,
        }
        if extra:
            record.update(extra)

        # Chain hash: sha256 of the JSON-serialized record (minus chain_hash itself)
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False)
        record["chain_hash"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        self._last_hash = record["chain_hash"]

        # Append
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def log_dry_run(self, entry: CleanEntry, tier: SafetyTier, msg: str) -> dict:
        return self.log_action("DRY_RUN", entry, msg, {"would_route_to": tier.value})

    def log_quarantine(self, entry: CleanEntry, dest: str) -> dict:
        return self.log_action("QUARANTINE", entry, f"moved to {dest}")

    def log_wipe(self, entry: CleanEntry) -> dict:
        return self.log_action("WIPE", entry, "unrecoverable delete")

    def log_protected_block(self, path: str) -> dict:
        return self.log_action("BLOCKED", None, f"protected path: {path}")

    def log_whitelist_add(self, entry: CleanEntry, reason: str) -> dict:
        return self.log_action("WL_ADD", entry, reason)

    def log_whitelist_health(self, rule_id: str, reason: str) -> dict:
        return self.log_action("WL_HEALTH", None, reason, {"rule_id": rule_id})

    def log_scan_start(self, config_summary: str) -> dict:
        return self.log_action("SCAN_START", None, config_summary)

    def log_scan_end(self, entry_count: int, total_bytes: int, elapsed_s: float) -> dict:
        return self.log_action(
            "SCAN_END", None,
            f"found {entry_count} entries, {_h(total_bytes)} in {elapsed_s:.1f}s",
        )

    def verify_chain(self) -> list[dict]:
        """Verify the chain integrity. Returns list of broken entries (empty = OK)."""
        if not self.path.exists():
            return []
        broken = []
        prev_hash = "genesis"
        with open(self.path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    broken.append({"line": line_num, "error": "invalid JSON"})
                    continue
                if entry.get("prev_hash") != prev_hash:
                    broken.append({
                        "line": line_num,
                        "error": "chain break",
                        "expected_prev": prev_hash,
                        "actual_prev": entry.get("prev_hash"),
                    })
                prev_hash = entry.get("chain_hash", "")
        return broken

    def recent(self, n: int = 50) -> list[dict]:
        """Return the last N audit entries."""
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries[-n:]


def _h(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if n >= 100 else f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
