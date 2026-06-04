"""Scan history + trend forecasting.

After each scan, a snapshot is appended to:
  ~/.cache/storage-analyzer/history.jsonl

Each snapshot contains:
  - timestamp
  - per-drive total_bytes, used_bytes, free_bytes
  - entry_count (how many cleanup candidates were found)
  - bytes_freed (how much was actually cleaned)

Forecasting:
  - Linear regression on the last N snapshots
  - Predicts "days until disk is full" and "growth rate per day"
  - If < 30 days until full → trigger warning

This module is intentionally simple (no heavy ML deps).
Linear regression is done with numpy-free formula.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_HISTORY_DIR = Path.home() / ".cache" / "storage-analyzer"
_HISTORY_FILE = _HISTORY_DIR / "history.jsonl"
_MAX_HISTORY = 365 * 3  # keep 3 years of daily snapshots


@dataclass
class DiskSnapshot:
    """A point-in-time snapshot of disk usage."""
    timestamp: float
    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    entry_count: int = 0       # cleanup candidates found
    bytes_freed: int = 0       # actually cleaned

    @property
    def usage_pct(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return self.used_bytes / self.total_bytes * 100


@dataclass
class Forecast:
    """Prediction from linear regression on history."""
    drive: str
    days_until_full: float | None  # None = can't predict (stable or shrinking)
    growth_per_day_bytes: float
    current_free_bytes: int
    current_usage_pct: float
    snapshots_used: int
    is_urgent: bool = False  # True if < 30 days until full


class HistoryStore:
    """JSONL-backed scan history."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _HISTORY_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, snapshot: DiskSnapshot) -> None:
        """Append a snapshot to the history log."""
        record = {
            "ts": snapshot.timestamp,
            "drive": snapshot.drive,
            "total": snapshot.total_bytes,
            "used": snapshot.used_bytes,
            "free": snapshot.free_bytes,
            "entries": snapshot.entry_count,
            "freed": snapshot.bytes_freed,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record_many(self, snapshots: list[DiskSnapshot]) -> None:
        """Batch-write multiple snapshots."""
        with open(self.path, "a", encoding="utf-8") as f:
            for s in snapshots:
                record = {
                    "ts": s.timestamp,
                    "drive": s.drive,
                    "total": s.total_bytes,
                    "used": s.used_bytes,
                    "free": s.free_bytes,
                    "entries": s.entry_count,
                    "freed": s.bytes_freed,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self, drive: str | None = None, limit: int = 90) -> list[DiskSnapshot]:
        """Load recent snapshots, optionally filtered by drive."""
        if not self.path.exists():
            return []
        snapshots = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if drive and r.get("drive") != drive:
                        continue
                    snapshots.append(DiskSnapshot(
                        timestamp=r["ts"],
                        drive=r["drive"],
                        total_bytes=r["total"],
                        used_bytes=r["used"],
                        free_bytes=r["free"],
                        entry_count=r.get("entries", 0),
                        bytes_freed=r.get("freed", 0),
                    ))
                except (json.JSONDecodeError, KeyError):
                    pass
        return snapshots[-limit:]

    def prune(self, max_entries: int = _MAX_HISTORY) -> None:
        """Keep only the last max_entries lines."""
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_entries:
            with open(self.path, "w", encoding="utf-8") as f:
                f.writelines(lines[-max_entries:])


class Forecaster:
    """Simple linear regression forecaster — no numpy needed."""

    def forecast(self, snapshots: list[DiskSnapshot]) -> Forecast | None:
        """Predict days until disk full based on historical free_bytes."""
        if len(snapshots) < 2:
            return None

        drive = snapshots[-1].drive
        current_free = snapshots[-1].free_bytes
        current_total = snapshots[-1].total_bytes
        usage_pct = snapshots[-1].usage_pct

        # Linear regression: free_bytes = a + b * time
        # We want to predict when free_bytes = 0
        xs = [s.timestamp for s in snapshots]
        ys = [s.free_bytes for s in snapshots]
        n = len(xs)

        # Normalize time to days from first snapshot
        t0 = xs[0]
        xs_norm = [(x - t0) / 86400.0 for x in xs]

        sum_x = sum(xs_norm)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs_norm, ys))
        sum_xx = sum(x * x for x in xs_norm)

        denom = n * sum_xx - sum_x * sum_x
        if abs(denom) < 1e-10:
            return Forecast(
                drive=drive,
                days_until_full=None,
                growth_per_day_bytes=0,
                current_free_bytes=current_free,
                current_usage_pct=usage_pct,
                snapshots_used=n,
            )

        b = (n * sum_xy - sum_x * sum_y) / denom
        a = (sum_y - b * sum_x) / n

        # b = slope of free_bytes per day (negative = disk filling up)
        growth_per_day = -b  # positive = bytes consumed per day

        if b >= 0:
            # Free space is growing or stable → can't predict "full"
            return Forecast(
                drive=drive,
                days_until_full=None,
                growth_per_day_bytes=growth_per_day,
                current_free_bytes=current_free,
                current_usage_pct=usage_pct,
                snapshots_used=n,
            )

        # b < 0: free space decreasing
        # days_until_full = current_free / |growth_per_day|
        days = current_free / abs(growth_per_day) if abs(growth_per_day) > 0 else None

        return Forecast(
            drive=drive,
            days_until_full=days,
            growth_per_day_bytes=growth_per_day,
            current_free_bytes=current_free,
            current_usage_pct=usage_pct,
            snapshots_used=n,
            is_urgent=(days is not None and days < 30),
        )


def take_snapshot(drive: str) -> DiskSnapshot | None:
    """Take a disk usage snapshot for a given drive/mount."""
    try:
        usage = shutil.disk_usage(drive)
        return DiskSnapshot(
            timestamp=time.time(),
            drive=drive,
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
        )
    except OSError:
        return None


def take_all_snapshots(drives: list[str]) -> list[DiskSnapshot]:
    """Snapshot multiple drives."""
    return [s for d in drives if (s := take_snapshot(d)) is not None]
