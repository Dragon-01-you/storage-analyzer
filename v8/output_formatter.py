"""Output formatter for user-friendly display.

Converts scan results into human-readable format with:
- Visual indicators (emoji-free, using ASCII)
- Size grouping
- Risk-based coloring
- Action recommendations
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .types import CleanEntry, RiskLevel, _human_bytes


@dataclass
class FormattedEntry:
    """A formatted entry for display."""
    name: str
    size: str
    risk: str
    category: str
    action: str
    path: str  # for internal use only


class OutputFormatter:
    """Format scan results for user-friendly display.

    Features:
    - Group by category
    - Sort by size
    - Risk indicators
    - Action recommendations
    - Summary statistics
    """

    # Risk level indicators
    RISK_INDICATORS = {
        "none": "[SAFE]",
        "low": "[LOW]",
        "med": "[MED]",
        "high": "[HIGH]",
    }

    # Action recommendations
    ACTION_MAP = {
        "none": "Auto-delete (safe)",
        "low": "Review recommended",
        "med": "Review required",
        "high": "Manual decision",
    }

    # Category display names
    CATEGORY_NAMES = {
        "system": "System",
        "dev": "Dev Tools",
        "browser": "Browsers",
        "chat": "Chat Apps",
        "cloud": "Cloud",
        "ide": "IDE",
        "gaming": "Gaming",
        "mail": "Email",
        "office": "Office",
        "media": "Media",
        "vm": "Virtual Machines",
    }

    def format_entries(
        self,
        entries: List[CleanEntry],
        show_path: bool = False,
        group_by: str = "category"
    ) -> str:
        """Format entries for display."""
        if not entries:
            return "No cleanup candidates found."

        lines = []
        lines.append("=" * 60)
        lines.append("STORAGE ANALYZER - SCAN RESULTS")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        total_size = sum(e.summary.total_bytes for e in entries)
        safe_size = sum(e.summary.total_bytes for e in entries if e.risk_level == RiskLevel.NONE)
        review_size = sum(e.summary.total_bytes for e in entries if e.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM))
        high_size = sum(e.summary.total_bytes for e in entries if e.risk_level == RiskLevel.HIGH)

        lines.append(f"Total found: {len(entries)} items ({_human_bytes(total_size)})")
        lines.append(f"  [SAFE]   Safe to delete: {_human_bytes(safe_size)}")
        lines.append(f"  [REVIEW] Needs review:   {_human_bytes(review_size)}")
        lines.append(f"  [HIGH]   High risk:      {_human_bytes(high_size)}")
        lines.append("")

        # Group entries
        if group_by == "category":
            groups = self._group_by_category(entries)
        elif group_by == "risk":
            groups = self._group_by_risk(entries)
        else:
            groups = {"All": entries}

        # Display groups
        for group_name, group_entries in groups.items():
            if not group_entries:
                continue

            group_size = sum(e.summary.total_bytes for e in group_entries)
            lines.append(f"--- {group_name} ({len(group_entries)} items, {_human_bytes(group_size)}) ---")
            lines.append("")

            # Sort by size (largest first)
            sorted_entries = sorted(group_entries, key=lambda e: e.summary.total_bytes, reverse=True)

            for entry in sorted_entries:
                risk = self.RISK_INDICATORS.get(entry.risk_level.value, "[?]")
                size = _human_bytes(entry.summary.total_bytes)
                action = self.ACTION_MAP.get(entry.risk_level.value, "Review")

                line = f"  {risk} {size:>10}  {entry.label.human_readable}"
                if show_path:
                    line += f"\n       Path: {entry.summary.path}"
                lines.append(line)

            lines.append("")

        # Recommendations
        lines.append("-" * 60)
        lines.append("RECOMMENDATIONS:")
        lines.append("")

        if safe_size > 0:
            lines.append(f"1. Quick cleanup: Delete [SAFE] items ({_human_bytes(safe_size)})")
        if review_size > 0:
            lines.append(f"2. Review [REVIEW] items ({_human_bytes(review_size)}) before deleting")
        if high_size > 0:
            lines.append(f"3. [HIGH] items ({_human_bytes(high_size)}) require manual decision")

        lines.append("")
        lines.append("To execute cleanup:")
        lines.append("  python run.py --execute          # Delete safe items only")
        lines.append("  python run.py --execute --all    # Delete all approved items")
        lines.append("")
        lines.append("-" * 60)

        return "\n".join(lines)

    def _group_by_category(self, entries: List[CleanEntry]) -> Dict[str, List[CleanEntry]]:
        """Group entries by category."""
        groups: Dict[str, List[CleanEntry]] = {}
        for entry in entries:
            cat = entry.label.category if hasattr(entry.label, 'category') else 'system'
            group_name = self.CATEGORY_NAMES.get(cat, cat.title())
            groups.setdefault(group_name, []).append(entry)
        return groups

    def _group_by_risk(self, entries: List[CleanEntry]) -> Dict[str, List[CleanEntry]]:
        """Group entries by risk level."""
        groups: Dict[str, List[CleanEntry]] = {
            "Safe to Delete": [],
            "Needs Review": [],
            "High Risk": [],
        }
        for entry in entries:
            if entry.risk_level == RiskLevel.NONE:
                groups["Safe to Delete"].append(entry)
            elif entry.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
                groups["Needs Review"].append(entry)
            else:
                groups["High Risk"].append(entry)
        return groups

    def format_json(self, entries: List[CleanEntry]) -> Dict[str, Any]:
        """Format entries as JSON structure."""
        result = {
            "ok": True,
            "total_items": len(entries),
            "total_bytes": sum(e.summary.total_bytes for e in entries),
            "total_human": _human_bytes(sum(e.summary.total_bytes for e in entries)),
            "categories": {},
            "risks": {
                "safe": {"count": 0, "bytes": 0},
                "review": {"count": 0, "bytes": 0},
                "high": {"count": 0, "bytes": 0},
            },
            "items": [],
        }

        for entry in entries:
            # Categories
            cat = entry.label.category if hasattr(entry.label, 'category') else 'system'
            if cat not in result["categories"]:
                result["categories"][cat] = {"count": 0, "bytes": 0}
            result["categories"][cat]["count"] += 1
            result["categories"][cat]["bytes"] += entry.summary.total_bytes

            # Risks
            if entry.risk_level == RiskLevel.NONE:
                result["risks"]["safe"]["count"] += 1
                result["risks"]["safe"]["bytes"] += entry.summary.total_bytes
            elif entry.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
                result["risks"]["review"]["count"] += 1
                result["risks"]["review"]["bytes"] += entry.summary.total_bytes
            else:
                result["risks"]["high"]["count"] += 1
                result["risks"]["high"]["bytes"] += entry.summary.total_bytes

            # Items
            result["items"].append({
                "name": entry.label.human_readable,
                "path": str(entry.summary.path),
                "size_bytes": entry.summary.total_bytes,
                "size_human": _human_bytes(entry.summary.total_bytes),
                "risk": entry.risk_level.value,
                "category": cat,
            })

        # Convert bytes to human readable
        for cat_data in result["categories"].values():
            cat_data["human"] = _human_bytes(cat_data["bytes"])
        for risk_data in result["risks"].values():
            risk_data["human"] = _human_bytes(risk_data["bytes"])

        return result


def format_scan_results(entries: List[CleanEntry], output_format: str = "text") -> str:
    """Convenience function to format scan results."""
    formatter = OutputFormatter()
    if output_format == "json":
        import json
        return json.dumps(formatter.format_json(entries), indent=2, ensure_ascii=False)
    else:
        return formatter.format_entries(entries)
