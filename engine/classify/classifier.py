"""Classifier module - handles classification and action generation."""
import re

from ..utils import CFG, hb


def classify_item(name, path, group, size_kb):
    """Classify a single item as green/red/yellow."""
    path_lower = path.lower().replace("\\", "/")
    name_lower = name.lower()
    
    # Check known_apps from config
    known = CFG.get("classify", {}).get("known_apps", {})
    for app_key, app_info in known.items():
        if app_key.lower() in name_lower or app_key.lower() in path_lower:
            return app_info[0], app_info[1], "med"
    
    # Check green/red rules from config
    classify_cfg = CFG.get("classify", {})
    for rule in classify_cfg.get("green", []):
        if re.search(rule["pat"], path, re.IGNORECASE):
            return "green", rule["reason"], rule.get("conf", "med")
    for rule in classify_cfg.get("red", []):
        if re.search(rule["pat"], path, re.IGNORECASE):
            return "red", rule["reason"], rule.get("conf", "med")
    
    # Heuristic fallbacks
    if group in ("temp", "windows_temp", "crash_dumps", "cbs_logs"):
        return "green", "Temp/system cache", "med"
    if group in ("local", "roaming"):
        return "yellow", "App data - review", "med"
    if group == "downloads":
        return "yellow", "Downloads - review", "low"
    return "yellow", "Unknown", "low"


def gen_actions(groups, sys_items, dry_run=True):
    """Generate action list from scan results."""
    actions = []
    seen = set()
    
    # System items with safe flag = auto-delete (green)
    for item in sys_items:
        path = item.get("p", "")
        name = item.get("n", "")
        if item.get("safe"):
            act = {
                "act": "delete",
                "what": item.get("reason", f"Delete {name}"),
                "path": path,
                "sz": item.get("h", "?"),
                "risk": item.get("risk", "none"),
                "prio": item.get("prio", 1),
                "cat": item.get("cat", "system"),
                "force": True
            }
            if item.get("dism"):
                act["dism"] = True
            actions.append(act)
        else:
            prefix = "[DRY-RUN] " if dry_run else ""
            actions.append({
                "act": "review",
                "what": f"{prefix}Review: {name} - {item.get('reason', 'Unknown')}",
                "path": path,
                "sz": item.get("h", "?"),
                "risk": item.get("risk", "med"),
                "prio": item.get("prio", 3),
                "cat": item.get("cat", "system")
            })
        seen.add(path)
    
    # Group items �� classify each
    for group, items in groups.items():
        for item in items:
            path = item.get("p", "")
            name = item.get("n", "")
            if path in seen:
                continue
            tier, reason, confidence = classify_item(name, path, group, item.get("k", 0))
            if tier == "green":
                actions.append({
                    "act": "delete",
                    "what": f"{name} ({reason})",
                    "path": path,
                    "sz": item.get("h", "?"),
                    "risk": "none",
                    "prio": 2,
                    "cat": group
                })
            elif tier == "red":
                actions.append({
                    "act": "keep",
                    "what": f"Protected: {name}",
                    "path": path,
                    "sz": item.get("h", "?"),
                    "risk": "none",
                    "prio": 5,
                    "cat": group
                })
            else:
                actions.append({
                    "act": "review",
                    "what": f"{name} - {reason}",
                    "path": path,
                    "sz": item.get("h", "?"),
                    "risk": "medium",
                    "prio": 3,
                    "cat": group
                })
            seen.add(path)
    
    actions.sort(key=lambda x: (x["prio"], -_parse_h(x.get("sz", "0B"))))
    return actions[:30]


def _parse_h(s):
    """Parse human-readable size string to bytes."""
    for m, u in [(1024**3, "GB"), (1024**2, "MB"), (1024**1, "KB"), (1, "B")]:
        if u in s:
            try:
                return float(s.replace(u, "")) * m
            except ValueError:
                pass
    return 0
