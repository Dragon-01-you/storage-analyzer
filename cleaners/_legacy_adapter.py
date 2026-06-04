"""Convert a list[Entry] into the legacy dict shape that gen_actions
expects, so the new cleaner pipeline can drop in as a replacement
for engine.scanner.scan_sys() without breaking anything.

Legacy item shape (used by engine.classify.gen_actions):

  {
    "n": "MEMORY.DMP",
    "p": "C:\\Windows\\MEMORY.DMP",
    "k": 15728640,
    "h": "15GB",
    "safe": True,
    "reason": "System memory dump",
    "risk": "none",
    "prio": 1,
    "cat": "system",
    "dism": False,         # optional
  }
"""
from __future__ import annotations
from typing import List, Dict, Any

from ._base import Entry


def entry_to_legacy(item: Entry) -> Dict[str, Any]:
    out = {
        "n": item.name,
        "p": item.path,
        "k": item.size_kb,
        "h": item.size_h,
        "safe": item.safe,
        "reason": item.reason,
        "risk": item.risk,
        "prio": item.prio,
        "cat": item.cat,
    }
    if item.needs_dism:
        out["dism"] = True
    if item.needs_recycle:
        out["dism"] = False  # legacy used a generic disim flag; keep consistent
    return out


def to_legacy_list(entries: List[Entry]) -> List[Dict[str, Any]]:
    return [entry_to_legacy(e) for e in entries]
