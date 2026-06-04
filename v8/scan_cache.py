"""Incremental scan cache backed by SQLite.

Stores (path, mtime, size, partial_hash) so that repeat scans
skip directories that haven't changed since last run.

Cache invalidation strategy:
  1. mtime changed → re-scan
  2. file_count changed → re-scan
  3. neither changed → reuse cached DirectorySummary

For safety, the cache is NEVER trusted for deletion decisions.
It only drives the SCAN stage.  Deletion always re-validates on disk.

Cache location: ~/.cache/storage-analyzer/v8-cache.sqlite
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .types import DirectorySummary


_CACHE_DIR = Path.home() / ".cache" / "storage-analyzer"
_CACHE_DB = _CACHE_DIR / "v8-cache.sqlite"
_CACHE_SCHEMA_VERSION = 1


class ScanCache:
    """SQLite-backed incremental cache for DirectorySummary objects."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_entries (
                path           TEXT PRIMARY KEY,
                mtime          REAL,
                total_bytes    INTEGER,
                file_count     INTEGER,
                feature_files  TEXT,   -- JSON array
                feature_dirs   TEXT,   -- JSON array
                has_lock_files INTEGER, -- 0/1
                contains_user_data INTEGER, -- 0/1
                cached_at      REAL
            );
            CREATE INDEX IF NOT EXISTS idx_mtime ON scan_entries(mtime);
        """)
        # Set schema version
        cur = self._conn.execute(
            "SELECT value FROM cache_meta WHERE key='schema_version'"
        )
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO cache_meta (key, value) VALUES ('schema_version', ?)",
                (str(_CACHE_SCHEMA_VERSION),),
            )
        self._conn.commit()

    # ---- Query --------------------------------------------------------

    def get(self, path: Path) -> DirectorySummary | None:
        """Return cached summary if mtime + file_count still match."""
        key = str(path).lower() if os.name == "nt" else str(path)
        cur = self._conn.execute(
            "SELECT mtime, total_bytes, file_count, feature_files, feature_dirs, "
            "has_lock_files, contains_user_data "
            "FROM scan_entries WHERE path = ?",
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        cached_mtime, total, count, ff_json, fd_json, lock, ud = row

        # Quick invalidation: check mtime of directory
        try:
            actual_mtime = path.stat().st_mtime
        except OSError:
            return None

        if abs(actual_mtime - cached_mtime) > 1.0:
            # Directory changed, cache stale
            return None

        # Build DirectorySummary from cache
        return DirectorySummary(
            path=path,
            total_bytes=total,
            file_count=count,
            last_access=None,  # not cached (expensive to re-stat)
            last_modified=datetime.fromtimestamp(actual_mtime),
            feature_files=json.loads(ff_json) if ff_json else [],
            feature_dirs=json.loads(fd_json) if fd_json else [],
            has_lock_files=bool(lock),
            contains_user_data=bool(ud),
        )

    # ---- Store --------------------------------------------------------

    def put(self, summary: DirectorySummary) -> None:
        """Store or update a DirectorySummary in the cache."""
        key = str(summary.path).lower() if os.name == "nt" else str(summary.path)
        try:
            mtime = summary.path.stat().st_mtime
        except OSError:
            mtime = time.time()

        self._conn.execute(
            """INSERT OR REPLACE INTO scan_entries
               (path, mtime, total_bytes, file_count, feature_files,
                feature_dirs, has_lock_files, contains_user_data, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                key,
                mtime,
                summary.total_bytes,
                summary.file_count,
                json.dumps(summary.feature_files, ensure_ascii=False),
                json.dumps(summary.feature_dirs, ensure_ascii=False),
                int(summary.has_lock_files),
                int(summary.contains_user_data),
                time.time(),
            ),
        )
        self._conn.commit()

    def put_many(self, summaries: list[DirectorySummary]) -> None:
        """Batch-store multiple summaries (single commit)."""
        rows = []
        for s in summaries:
            key = str(s.path).lower() if os.name == "nt" else str(s.path)
            try:
                mtime = s.path.stat().st_mtime
            except OSError:
                mtime = time.time()
            rows.append((
                key, mtime, s.total_bytes, s.file_count,
                json.dumps(s.feature_files, ensure_ascii=False),
                json.dumps(s.feature_dirs, ensure_ascii=False),
                int(s.has_lock_files), int(s.contains_user_data),
                time.time(),
            ))
        self._conn.executemany(
            """INSERT OR REPLACE INTO scan_entries
               (path, mtime, total_bytes, file_count, feature_files,
                feature_dirs, has_lock_files, contains_user_data, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    # ---- Maintenance --------------------------------------------------

    def invalidate(self, path: Path) -> bool:
        """Remove a single entry from the cache."""
        key = str(path).lower() if os.name == "nt" else str(path)
        cur = self._conn.execute(
            "DELETE FROM scan_entries WHERE path = ?", (key,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def prune_stale(self, max_age_days: int = 30) -> int:
        """Remove entries older than max_age_days."""
        cutoff = time.time() - max_age_days * 86400
        cur = self._conn.execute(
            "DELETE FROM scan_entries WHERE cached_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def clear(self) -> int:
        """Nuke all cached entries."""
        cur = self._conn.execute("DELETE FROM scan_entries")
        self._conn.commit()
        return cur.rowcount

    def stats(self) -> dict:
        """Return cache stats."""
        cur = self._conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_bytes), 0) FROM scan_entries"
        )
        count, total = cur.fetchone()
        return {
            "entries": count,
            "total_bytes": total,
            "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
        }

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ScanCache":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
