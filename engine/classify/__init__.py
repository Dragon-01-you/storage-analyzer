"""Classification subsystem.

Public:
  classify_item(name, path, group, size_kb) -> (tier, reason, confidence)
  gen_actions(groups, sys_items, dry_run)   -> list[action]
  _parse_h(s)                                -> int (bytes)
  ai_judge                                    -> submodule (AI judge seam)
"""
from .classifier import classify_item, gen_actions, _parse_h
from . import ai_judge  # noqa: F401  (submodule, not a function)

__all__ = ["classify_item", "gen_actions", "_parse_h", "ai_judge"]
