"""Reusable cleanup plan system.

Inspired by windows-disk-cleaner-skill's plan system:
- Scan once, clean multiple times
- Save plan to file
- Resume from saved plan
- Track cleanup history
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class PlanItem:
    """A single item in a cleanup plan."""
    path: str
    name: str
    size_bytes: int
    category: str
    risk: str  # 'safe', 'review', 'high'
    status: str = 'pending'  # 'pending', 'approved', 'skipped', 'deleted', 'failed'
    reason: str = ''
    approved_at: str = ''
    deleted_at: str = ''

    @property
    def size_human(self) -> str:
        from .types import _human_bytes
        return _human_bytes(self.size_bytes)


@dataclass
class CleanupPlan:
    """A reusable cleanup plan."""
    plan_id: str
    created_at: str
    updated_at: str
    scan_paths: List[str]
    items: List[PlanItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items)

    @property
    def approved_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items if item.status == 'approved')

    @property
    def deleted_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items if item.status == 'deleted')

    @property
    def pending_count(self) -> int:
        return sum(1 for item in self.items if item.status == 'pending')

    @property
    def approved_count(self) -> int:
        return sum(1 for item in self.items if item.status == 'approved')

    @property
    def deleted_count(self) -> int:
        return sum(1 for item in self.items if item.status == 'deleted')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'scan_paths': self.scan_paths,
            'items': [asdict(item) for item in self.items],
            'metadata': self.metadata,
            'summary': {
                'total_bytes': self.total_bytes,
                'approved_bytes': self.approved_bytes,
                'deleted_bytes': self.deleted_bytes,
                'pending_count': self.pending_count,
                'approved_count': self.approved_count,
                'deleted_count': self.deleted_count,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CleanupPlan':
        items = [PlanItem(**item) for item in data.get('items', [])]
        return cls(
            plan_id=data['plan_id'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            scan_paths=data['scan_paths'],
            items=items,
            metadata=data.get('metadata', {}),
        )


class PlanManager:
    """Manage cleanup plans.

    Features:
    - Create new plan from scan results
    - Save/load plans
    - Approve/skip items
    - Execute approved items
    - Track history
    """

    def __init__(self, plans_dir: str = None) -> None:
        if plans_dir is None:
            if os.name == 'nt':
                plans_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                                         'StorageAnalyzer', 'plans')
            else:
                plans_dir = os.path.join(os.path.expanduser('~'), '.cache', 'storage-analyzer', 'plans')
        self.plans_dir = plans_dir
        os.makedirs(plans_dir, exist_ok=True)

    def create_plan(self, scan_paths: List[str], items: List[Dict[str, Any]]) -> CleanupPlan:
        """Create a new cleanup plan from scan results."""
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        now = datetime.now().isoformat()

        plan_items = []
        for item in items:
            plan_items.append(PlanItem(
                path=item.get('path', ''),
                name=item.get('name', ''),
                size_bytes=item.get('size_bytes', 0),
                category=item.get('category', 'unknown'),
                risk=item.get('risk', 'review'),
                reason=item.get('reason', ''),
            ))

        plan = CleanupPlan(
            plan_id=plan_id,
            created_at=now,
            updated_at=now,
            scan_paths=scan_paths,
            items=plan_items,
        )

        return plan

    def save_plan(self, plan: CleanupPlan) -> str:
        """Save plan to file."""
        plan.updated_at = datetime.now().isoformat()
        filepath = os.path.join(self.plans_dir, f"{plan.plan_id}.json")

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)

        return filepath

    def load_plan(self, plan_id: str) -> Optional[CleanupPlan]:
        """Load plan from file."""
        filepath = os.path.join(self.plans_dir, f"{plan_id}.json")
        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return CleanupPlan.from_dict(data)

    def list_plans(self) -> List[Dict[str, Any]]:
        """List all saved plans."""
        plans = []
        for filename in os.listdir(self.plans_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.plans_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    plans.append({
                        'plan_id': data['plan_id'],
                        'created_at': data['created_at'],
                        'item_count': len(data.get('items', [])),
                        'total_bytes': data.get('summary', {}).get('total_bytes', 0),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        return plans

    def approve_item(self, plan: CleanupPlan, item_path: str) -> bool:
        """Approve an item for deletion."""
        for item in plan.items:
            if item.path == item_path:
                item.status = 'approved'
                item.approved_at = datetime.now().isoformat()
                return True
        return False

    def approve_all_safe(self, plan: CleanupPlan) -> int:
        """Approve all safe items."""
        count = 0
        for item in plan.items:
            if item.risk == 'safe' and item.status == 'pending':
                item.status = 'approved'
                item.approved_at = datetime.now().isoformat()
                count += 1
        return count

    def skip_item(self, plan: CleanupPlan, item_path: str) -> bool:
        """Skip an item."""
        for item in plan.items:
            if item.path == item_path:
                item.status = 'skipped'
                return True
        return False

    def execute_plan(self, plan: CleanupPlan, dry_run: bool = True) -> Dict[str, Any]:
        """Execute approved items in the plan."""
        results = {
            'deleted': [],
            'failed': [],
            'skipped': [],
        }

        for item in plan.items:
            if item.status != 'approved':
                results['skipped'].append(item.path)
                continue

            if dry_run:
                results['deleted'].append({
                    'path': item.path,
                    'size': item.size_bytes,
                    'dry_run': True,
                })
                continue

            try:
                os.remove(item.path)
                item.status = 'deleted'
                item.deleted_at = datetime.now().isoformat()
                results['deleted'].append({
                    'path': item.path,
                    'size': item.size_bytes,
                })
            except OSError as e:
                item.status = 'failed'
                results['failed'].append({
                    'path': item.path,
                    'error': str(e),
                })

        return results

    def get_plan_summary(self, plan: CleanupPlan) -> str:
        """Get human-readable plan summary."""
        from .types import _human_bytes

        lines = []
        lines.append(f"Plan: {plan.plan_id}")
        lines.append(f"Created: {plan.created_at}")
        lines.append(f"Paths: {', '.join(plan.scan_paths)}")
        lines.append("")
        lines.append(f"Total: {len(plan.items)} items ({_human_bytes(plan.total_bytes)})")
        lines.append(f"  Pending:  {plan.pending_count}")
        lines.append(f"  Approved: {plan.approved_count}")
        lines.append(f"  Deleted:  {plan.deleted_count}")
        lines.append("")

        # Group by category
        categories = {}
        for item in plan.items:
            cat = item.category
            if cat not in categories:
                categories[cat] = {'count': 0, 'bytes': 0}
            categories[cat]['count'] += 1
            categories[cat]['bytes'] += item.size_bytes

        lines.append("By category:")
        for cat, info in sorted(categories.items(), key=lambda x: -x[1]['bytes']):
            lines.append(f"  {cat}: {info['count']} items ({_human_bytes(info['bytes'])})")

        return "\n".join(lines)


class MigrationPlanner:
    """Plan data migration from C: to other drives.

    Inspired by windows-disk-cleaner-skill's migration strategy.
    """

    # Directories that can be migrated
    MIGRATABLE = {
        'Downloads': 'User downloads',
        'Documents': 'User documents',
        'Desktop': 'Desktop files',
        'Pictures': 'Pictures',
        'Videos': 'Videos',
        'Music': 'Music',
        'node_modules': 'Node.js dependencies',
        '.npm': 'npm cache',
        '.cargo': 'Rust cargo cache',
        '.gradle': 'Gradle cache',
        '.m2': 'Maven cache',
        'Docker': 'Docker data',
        'Steam': 'Steam games',
        'Epic Games': 'Epic Games',
    }

    def analyze_migration(self, source_drive: str = 'C:', target_drive: str = 'D:') -> Dict[str, Any]:
        """Analyze what can be migrated."""
        home = os.path.expanduser('~')
        results = {
            'source': source_drive,
            'target': target_drive,
            'migratable': [],
            'total_bytes': 0,
        }

        for dirname, description in self.MIGRATABLE.items():
            # Check common locations
            paths_to_check = [
                os.path.join(home, dirname),
                os.path.join(home, 'AppData', 'Local', dirname),
                os.path.join(home, 'AppData', 'Roaming', dirname),
            ]

            for path in paths_to_check:
                if os.path.exists(path) and os.path.isdir(path):
                    try:
                        size = self._get_dir_size(path)
                        if size > 100 * 1024 * 1024:  # >100MB
                            results['migratable'].append({
                                'path': path,
                                'name': dirname,
                                'description': description,
                                'size_bytes': size,
                                'target': os.path.join(target_drive, os.path.relpath(path, source_drive)),
                            })
                            results['total_bytes'] += size
                    except OSError:
                        continue

        return results

    def _get_dir_size(self, path: str) -> int:
        """Get directory size."""
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        continue
        except OSError:
            pass
        return total

    def create_migration_plan(self, items: List[Dict[str, Any]]) -> str:
        """Create a migration script."""
        lines = []
        lines.append("# Migration Plan")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append("#")
        lines.append("# WARNING: Review this script before running!")
        lines.append("#")
        lines.append("")

        for item in items:
            source = item['path']
            target = item['target']
            lines.append(f"# {item['name']}: {item['description']}")
            lines.append(f"# Size: {item['size_bytes'] / (1024**3):.2f} GB")
            lines.append(f'robocopy "{source}" "{target}" /E /MOVE /R:3 /W:5')
            lines.append(f'mklink /D "{source}" "{target}"')
            lines.append("")

        return "\n".join(lines)
