"""Cleaner plugin abstraction.

Why:
  v6 / v7 of storage-analyzer hardcoded every cleanup target inside
  a 400+ line `scan_sys()` function in `engine/scanner.py`. Adding a
  new target required editing scanner.py and risking a regression.

  This module defines the contract every cleanup target must satisfy.
  One file per target. Trivial to add. Easy to test.

Lifecycle:
  1. cleaner.analyze(ctx)        -> list[Entry]
  2. user / AI reviews           -> may mutate risk / act
  3. cleaner.clean(entries, mode) -> Result

Each cleaner is a *class*, not a module-level function, so it can
hold config (paths, thresholds) and be re-instantiated per scan.

Discovery:
  Built-in cleaners are registered explicitly in
  `cleaners/registry.py` (avoid import magic so static analysis works).
  Third-party cleaners can be added via Python `entry_points`
  (group = "storage_analyzer.cleaners") -- not wired in v7.1 yet.
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    """A single cleanup candidate produced by a cleaner."""
    name: str
    path: str
    size_kb: int
    size_h: str
    reason: str
    risk: str            # "none" | "med" | "high"
    prio: int = 3        # 1 = highest, 5 = lowest
    cat: str = "system"
    safe: bool = True    # if True, eligible for one-click delete
    needs_recycle: bool = False
    needs_dism: bool = False
    needs_privilege: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Result:
    """Outcome of `clean(entries, mode)`.

    mode: "dry-run" | "execute" | "report"
    """
    ok: bool
    deleted: int = 0
    failed: int = 0
    skipped: int = 0
    freed_bytes: int = 0
    notes: List[str] = field(default_factory=list)
    audit: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Context (passed into each analyze())
# ---------------------------------------------------------------------------

@dataclass
class ScanContext:
    """Shared state passed to every cleaner's analyze().

    Built once per scan in `cleaners.runner.run_all()`.
    """
    home: str
    system_root: str
    is_windows: bool
    is_macos: bool
    is_linux: bool
    pp: Dict[str, Any]           # engine.plat_paths() output
    config: Dict[str, Any]       # full loaded config.json
    protected: set               # resolved protected paths

    @classmethod
    def build(cls) -> "ScanContext":
        from engine.utils import HOME, SYSROOT, IS_WIN, IS_MAC, IS_LINUX, PP, CFG, PROTECTED
        return cls(
            home=HOME,
            system_root=SYSROOT,
            is_windows=IS_WIN,
            is_macos=IS_MAC,
            is_linux=IS_LINUX,
            pp=PP,
            config=CFG,
            protected=PROTECTED,
        )


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Cleaner:
    """Subclass this to add a new cleanup target.

    Subclass contract:
      - Set the four class attributes below
      - Implement analyze(ctx) -> list[Entry]
      - (Optional) Override clean(entries, mode) for non-trivial targets

    The default `clean()` uses the safe_delete() pipeline from the
    engine, so most subclasses can ship with just `analyze()`.
    """

    # ---- Subclass-overridable metadata ---------------------------------
    name: str = "UnnamedCleaner"
    platforms: tuple = ("windows", "macos", "linux")
    risk_level: str = "none"          # none | med | high
    requires_privilege: bool = False
    category: str = "system"          # system | dev | browser | cloud | chat | ide | gaming | mail
    description: str = ""

    # ---- Required API --------------------------------------------------
    def analyze(self, ctx: ScanContext) -> List[Entry]:  # pragma: no cover
        raise NotImplementedError

    # ---- Default clean (good for 90% of cases) ------------------------
    def clean(self, entries: List[Entry], mode: str = "dry-run") -> Result:
        """Default implementation: iterate entries, call safe_delete.

        Subclasses override this for things like DISM, Recycle Bin,
        or app-specific protocols (npm cache clean --force, etc.).
        """
        from engine.deleter import safe_delete
        from engine.utils import audit_log

        result = Result(ok=True)
        for e in entries:
            if mode == "dry-run":
                result.notes.append(f"[dry-run] would clean {e.name} ({e.size_h})")
                result.skipped += 1
                continue
            ok, reason = safe_delete(
                e.path,
                force=True,
                is_dism=e.needs_dism,
                is_recycle=e.needs_recycle,
            )
            audit_log("DELETE" if ok else "FAIL", e.path, str(reason), e.size_kb * 1024)
            if ok:
                result.deleted += 1
                result.freed_bytes += e.size_kb * 1024
            else:
                result.failed += 1
            result.audit.append({
                "path": e.path, "ok": ok, "reason": str(reason),
                "size_kb": e.size_kb,
            })
        return result

    # ---- Helpers --------------------------------------------------------
    def supported_on(self, ctx: ScanContext) -> bool:
        if self.is_windows_only() and not ctx.is_windows:
            return False
        if self.is_macos_only() and not ctx.is_macos:
            return False
        if self.is_linux_only() and not ctx.is_linux:
            return False
        return True

    def is_windows_only(self) -> bool:
        return self.platforms == ("windows",)

    def is_macos_only(self) -> bool:
        return self.platforms == ("macos",)

    def is_linux_only(self) -> bool:
        return self.platforms == ("linux",)

    def __repr__(self) -> str:
        return f"<Cleaner {self.name} risk={self.risk_level} priv={self.requires_privilege}>"
