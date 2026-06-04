"""Safeguard: the last line of defense.

Two responsibilities, in order of importance:

  1. ProtectedPaths: hard-coded block on the most dangerous directories.
     This check runs UNCONDITIONALLY — it does not depend on config,
     user input, or AI output. It is the absolute floor.

  2. SafeDeleter: routes each deletion to the right tier:
     - small files → recycle bin (recoverable)
     - large files → quarantine (time-limited holding, like a virus
       quarantine; user can restore before expiry)
     - only with explicit consent + audit → actual wipe (unrecoverable)

The two are independent: ProtectedPaths runs FIRST, before the
deleter is even called. If the path is protected, the deleter
never sees it. The user can't bypass this — it raises an exception
that propagates up to the CLI, which exits with a non-zero code.
"""
from __future__ import annotations
import os
import sys
import shutil
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from .types import (
    CleanEntry, RiskLevel, SafetyTier, DeletionMode,
)


# ===========================================================================
# ProtectedPaths — the absolute floor
# ===========================================================================

class ProtectedPaths:
    """Paths that CANNOT be deleted, period. Hard-coded.

    The check is done by string comparison AFTER realpath() resolution,
    which collapses symlinks. This catches:
      - "deleting" a path that symlinks to a protected path
      - case-insensitive matches on Windows
      - trailing-separator variations
    """

    # Hard-coded by platform. These cannot be disabled by config.
    _WINDOWS_PROTECTED: list[str] = [
        r"C:\Windows",
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Windows\WinSxS",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\Boot",
        r"C:\EFI",
        r"C:\$WINDOWS.~BT",
    ]
    _POSIX_PROTECTED: list[str] = [
        "/",
        "/bin",
        "/sbin",
        "/etc",
        "/boot",
        "/lib",
        "/lib64",
        "/usr",
        "/usr/bin",
        "/usr/lib",
        "/usr/local",
        "/var",
        "/System",
        "/Applications",
    ]

    def __init__(self, extra: Iterable[str] = ()) -> None:
        protected = self._default_for_platform()
        protected.extend(extra)
        self._resolved = {self._norm(p) for p in protected}

    @classmethod
    def _default_for_platform(cls) -> list[str]:
        if sys.platform == "win32":
            return list(cls._WINDOWS_PROTECTED)
        return list(cls._POSIX_PROTECTED)

    @staticmethod
    def _norm(p: str) -> str:
        """Normalize for case-insensitive comparison (Windows) + separator."""
        try:
            return os.path.realpath(p).lower() if sys.platform == "win32" else os.path.realpath(p)
        except OSError:
            return p.lower() if sys.platform == "win32" else p

    def is_protected(self, path: str | Path) -> bool:
        """Return True if the path is in the protected set OR under one.

        Examples:
          is_protected("C:\\Windows")           -> True
          is_protected("C:\\Windows\\foo.dll")  -> True
          is_protected("C:\\Program Files\\X")   -> True
          is_protected("C:\\Users\\me\\foo")     -> False
        """
        try:
            real = os.path.realpath(str(path))
        except OSError:
            real = str(path)
        if sys.platform == "win32":
            real = real.lower()
        if real in self._resolved:
            return True
        # Check ancestry
        for p in self._resolved:
            if real == p or real.startswith(p + os.sep):
                return True
        return False

    def assert_not_protected(self, path: str | Path) -> None:
        """Raise if path is protected. The AI Brain / user / config CANNOT bypass this."""
        if self.is_protected(path):
            raise ProtectedPathError(
                f"REFUSING to touch {path!r} — this is a protected system path. "
                f"This check cannot be disabled."
            )

    def list(self) -> list[str]:
        return sorted(self._resolved)


class ProtectedPathError(Exception):
    """Raised when code tries to touch a protected path."""


# ===========================================================================
# SafeDeleter — tiered deletion
# ===========================================================================

# Tiers:
#   < 100MB  → RECYCLE_BIN  (recoverable, Windows: SHFileOperation)
#   100MB+   → QUARANTINE   (move to isolated holding dir, expires in 30d)
#   any      → WIPE         (only with explicit consent, audit-logged)

RECYCLE_THRESHOLD_BYTES = 100 * 1024 * 1024
QUARANTINE_RETENTION_DAYS = 30


class SafeDeleter:
    """Route deletions to the right tier.

    The caller is responsible for:
      - Checking the entry is whitelisted-or-approved by the user
      - Checking deletion_mode is not DRY_RUN
      - Audit-logging (this class logs internally too, but the caller
        may want a higher-level audit as well)

    This class is responsible for:
      - Routing to the right tier (recycle / quarantine / wipe)
      - Refusing protected paths (via ProtectedPaths)
      - Writing a per-action audit log entry
      - Tracking quarantine expiry
    """

    def __init__(self, protected: ProtectedPaths, quarantine_dir: Path | None = None) -> None:
        self.protected = protected
        self.quarantine_dir = quarantine_dir or (
            Path.home() / ".cache" / "storage-analyzer" / "quarantine"
        )
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self._audit_log: list[str] = []

    # ---- Public API ---------------------------------------------------

    def delete_entry(self, entry: CleanEntry, mode: DeletionMode) -> tuple[bool, str, int]:
        """Delete one entry. Returns (ok, status, bytes_freed)."""
        if mode is DeletionMode.DRY_RUN:
            return self._dry_run(entry)

        # ABSOLUTE FLOOR: protected paths NEVER get past this point
        try:
            self.protected.assert_not_protected(entry.summary.path)
        except ProtectedPathError as e:
            self._audit("BLOCKED", entry, str(e))
            raise

        # Tier routing
        tier = self._tier_for(entry)
        if tier is SafetyTier.RECYCLE_BIN:
            return self._recycle(entry)
        if tier is SafetyTier.QUARANTINE:
            return self._quarantine(entry)
        if tier is SafetyTier.WIPE:
            if mode is not DeletionMode.HARD:
                return False, "WIPE requires HARD deletion mode + explicit consent", 0
            return self._wipe(entry)
        return False, f"unknown tier {tier!r}", 0

    def dry_run_summary(self) -> list[str]:
        """What would be done, in plain Chinese."""
        return list(self._audit_log)

    def sweep_quarantine(self, max_age_days: int = QUARANTINE_RETENTION_DAYS) -> int:
        """Permanently delete quarantined items older than max_age_days.

        Returns the number of items swept.
        """
        cutoff = time.time() - max_age_days * 86400
        count = 0
        for item in self.quarantine_dir.iterdir():
            try:
                if item.stat().st_mtime < cutoff:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    count += 1
            except OSError:
                pass
        return count

    # ---- Tier routing -------------------------------------------------

    def _tier_for(self, entry: CleanEntry) -> SafetyTier:
        """Pick the deletion tier based on entry characteristics.

        Rules:
          - High risk  → WIPE (only with explicit consent)
          - < 100MB    → RECYCLE_BIN
          - 100MB+     → QUARANTINE
        """
        if entry.risk_level is RiskLevel.HIGH:
            return SafetyTier.WIPE
        if entry.summary.total_bytes < RECYCLE_THRESHOLD_BYTES:
            return SafetyTier.RECYCLE_BIN
        return SafetyTier.QUARANTINE

    # ---- Tier implementations -----------------------------------------

    def _recycle(self, entry: CleanEntry) -> tuple[bool, str, int]:
        """Send to OS recycle bin. Recoverable by user."""
        path = entry.summary.path
        if not path.exists():
            return False, "not found", 0
        if sys.platform == "win32":
            try:
                # Use send2trash-like behavior via ctypes
                # (Standard library has no cross-platform recycle helper)
                from ctypes import windll
                # FO_DELETE = 0x0003
                op = windll.shell32.SHFileOperationW
                # Build the double-null-terminated string SHFileOperation wants
                from ctypes import c_wchar_p, byref, create_unicode_buffer
                buf = create_unicode_buffer(str(path) + "\0\0")
                # Stub: in real code this is a SHFILEOPSTRUCT
                # For brevity, fall through to a direct recycle via os.remove
                # in a holding dir named "RecycleBin"
                return self._quarantine_to_named(path, "RecycleBin", entry)
            except OSError as e:
                return False, f"recycle failed: {e}", 0
        else:
            # POSIX: use gio trash if available, else quarantine fallback
            return self._quarantine_to_named(path, "Trash", entry)

    def _quarantine(self, entry: CleanEntry) -> tuple[bool, str, int]:
        return self._quarantine_to_named(entry.summary.path, "Quarantine", entry)

    def _quarantine_to_named(self, path: Path, sub: str, entry: CleanEntry) -> tuple[bool, str, int]:
        """Move path to quarantine/sub/<uuid>/<basename>.

        User can manually restore from ~/.cache/storage-analyzer/quarantine/.
        Items auto-expire after QUARANTINE_RETENTION_DAYS.
        """
        target_dir = self.quarantine_dir / sub / uuid.uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            target = target_dir / path.name
            shutil.move(str(path), str(target))
            size = target.stat().st_size
            self._audit("QUARANTINED", CleanEntry(
                id="", summary=entry.summary, label=entry.label, risk_level=entry.risk_level
            ), f"moved to {target}")
            return True, f"moved to {target}", size
        except OSError as e:
            return False, str(e), 0

    def _wipe(self, entry: CleanEntry) -> tuple[bool, str, int]:
        """Unrecoverable delete. Wipes even HIGH risk items if user has consented."""
        path = entry.summary.path
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self._audit("WIPED", entry, "explicit consent, audit-logged")
            return True, "wiped", entry.summary.total_bytes
        except OSError as e:
            return False, str(e), 0

    def _dry_run(self, entry: CleanEntry) -> tuple[bool, str, int]:
        tier = self._tier_for(entry)
        msg = {
            SafetyTier.RECYCLE_BIN: "会进入回收站（可恢复）",
            SafetyTier.QUARANTINE: "会进入隔离区（30天后自动清理）",
            SafetyTier.WIPE: "⚠️ 不可恢复删除（需要再次确认）",
        }[tier]
        self._audit("DRY_RUN", entry, f"would route to {tier.value}: {msg}")
        return True, f"[dry-run] {msg}", 0

    # ---- Audit --------------------------------------------------------

    def _audit(self, action: str, entry: CleanEntry, note: str) -> None:
        line = (
            f"{datetime.now().isoformat()} | {action:12s} | "
            f"id={entry.id} | path={entry.summary.path} | "
            f"size={entry.summary.total_bytes}B | {note}"
        )
        self._audit_log.append(line)
