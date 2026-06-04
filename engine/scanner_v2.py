"""Scanner v2 - runs the cleaner plugin pipeline.

This is the new code path; the legacy `engine.scanner.scan_sys()`
is preserved for backward compatibility. `engine.main` chooses
between them based on the `use_cleaners` opt (default: legacy).

The two outputs are equivalent in shape (list of dicts with the
same keys gen_actions reads), so swapping them in is a one-liner.

Import order note:
  This module is imported at `engine/__init__.py` load time, which
  happens BEFORE `cleaners/__init__.py` finishes loading. So we
  import cleaners lazily, inside the function, to avoid the
  circular dependency.
"""
from __future__ import annotations
from typing import List, Dict, Any


def scan_sys_v2() -> List[Dict[str, Any]]:
    """Run every registered cleaner and return legacy-shaped items."""
    # Lazy import to break the engine <-> cleaners circular dep
    from cleaners import run_all, ScanContext, to_legacy_list
    ctx = ScanContext.build()
    entries = run_all(ctx)
    return to_legacy_list(entries)


def scan_sys_v2_for_categories(categories) -> List[Dict[str, Any]]:
    """Like scan_sys_v2() but only run cleaners in the given categories."""
    from cleaners import run_all, ScanContext, to_legacy_list
    ctx = ScanContext.build()
    entries = run_all(ctx, categories=set(categories))
    return to_legacy_list(entries)


__all__ = ["scan_sys_v2", "scan_sys_v2_for_categories"]
