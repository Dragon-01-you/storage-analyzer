"""Safe Cleanup - Cleanup with absolute safety.

This module ensures:
1. NEVER delete user software without explicit confirmation
2. ALWAYS show what will be deleted before deleting
3. Require user approval for every deletion
4. Maintain audit log of all operations

All deletions go through the Safeguard layer (ProtectedPaths check,
tiered deletion routing, audit logging). No direct os.remove / shutil.rmtree.
"""
from __future__ import annotations
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .types import (
    _human_bytes, CleanEntry, DirectorySummary, CognitiveLabel,
    RiskLevel, LabelSource, DeletionMode,
)
from .safety_guard import SafetyGuard, DeletionRequest
from .safeguard import ProtectedPaths, SafeDeleter


@dataclass
class CleanupItem:
    """An item to be cleaned up."""
    path: str
    name: str
    size: int
    category: str  # SAFE, REVIEW, PROTECTED
    reason: str
    can_delete: bool
    requires_approval: bool


class SafeCleanup:
    """Cleanup with absolute safety mechanisms.

    All deletions route through SafeDeleter, which enforces:
    - ProtectedPaths hard-block on system directories
    - Tiered deletion (recycle bin / quarantine / wipe)
    - Per-action audit logging
    """

    def __init__(self, deletion_mode: DeletionMode = DeletionMode.DRY_RUN):
        self.deletion_mode = deletion_mode
        self.safety_guard = SafetyGuard()
        self.protected = ProtectedPaths()
        self.deleter = SafeDeleter(protected=self.protected)
        self.cleanup_items: list[CleanupItem] = []
        self.approved_items: list[CleanupItem] = []
        self.denied_items: list[CleanupItem] = []
        self.deleted_items: list[CleanupItem] = []
        self.freed_bytes: int = 0
    
    def scan_directory(self, path: str, max_depth: int = 3) -> list[CleanupItem]:
        """Scan a directory and categorize items."""
        items = []
        path_obj = Path(path)
        
        if not path_obj.exists():
            return items
        
        try:
            for item in path_obj.rglob('*'):
                if len(item.relative_to(path_obj).parts) > max_depth:
                    continue
                
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        if size > 10 * 1024 * 1024:  # >10MB
                            category = self._categorize_item(str(item))
                            items.append(CleanupItem(
                                path=str(item),
                                name=item.name,
                                size=size,
                                category=category,
                                reason=self._get_reason(str(item), category),
                                can_delete=category != 'PROTECTED',
                                requires_approval=category == 'REVIEW',
                            ))
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass
        
        return items
    
    def _categorize_item(self, path: str) -> str:
        """Categorize an item as SAFE, REVIEW, or PROTECTED."""
        # Check if protected
        is_protected, _ = self.safety_guard.is_protected(path)
        if is_protected:
            return 'PROTECTED'
        
        # Check if safe to delete
        safe_patterns = [
            'cache', 'temp', 'tmp', 'log', 'crashdump',
            'node_modules', '__pycache__', '.next', 'build', 'dist',
        ]
        
        path_lower = path.lower()
        for pattern in safe_patterns:
            if pattern in path_lower:
                return 'SAFE'
        
        # Default to REVIEW
        return 'REVIEW'
    
    def _get_reason(self, path: str, category: str) -> str:
        """Get reason for categorization."""
        if category == 'PROTECTED':
            return 'User software or important data'
        elif category == 'SAFE':
            return 'Cache or temporary files'
        else:
            return 'Requires user review'
    
    def request_approval(self, item: CleanupItem) -> DeletionRequest:
        """Request approval for deletion."""
        return self.safety_guard.request_deletion(
            path=item.path,
            name=item.name,
            size=item.size,
            category=item.category,
            reason=item.reason,
        )
    
    def approve_item(self, item: CleanupItem):
        """Approve an item for deletion."""
        self.approved_items.append(item)
    
    def deny_item(self, item: CleanupItem):
        """Deny an item for deletion."""
        self.denied_items.append(item)
    
    @staticmethod
    def _item_to_entry(item: CleanupItem) -> CleanEntry:
        """Convert a CleanupItem into a CleanEntry for SafeDeleter."""
        path = Path(item.path)
        # Stable short id from path hash
        entry_id = hashlib.sha256(item.path.encode()).hexdigest()[:12]
        summary = DirectorySummary(
            path=path,
            total_bytes=item.size,
            file_count=1,
        )
        # Map category to risk level
        risk_map = {
            'SAFE': RiskLevel.LOW,
            'REVIEW': RiskLevel.MEDIUM,
            'PROTECTED': RiskLevel.HIGH,
        }
        risk = risk_map.get(item.category, RiskLevel.MEDIUM)
        label = CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label=item.name,
            human_readable_risk=item.reason,
            confidence=1.0,
            suggested_action="delete_safely" if item.can_delete else "keep",
        )
        return CleanEntry(
            id=entry_id,
            summary=summary,
            label=label,
            risk_level=risk,
        )

    def delete_approved_items(self) -> int:
        """Delete only approved items via SafeDeleter.

        Every deletion goes through:
        1. ProtectedPaths assert (blocks system dirs)
        2. Tiered routing (recycle / quarantine / wipe)
        3. Audit logging
        """
        deleted_count = 0

        for item in self.approved_items:
            try:
                # Block protected paths at the SafeCleanup level too
                if self.protected.is_protected(item.path):
                    print(f"  [BLOCKED] Protected path, skipping: {item.name}")
                    continue

                entry = self._item_to_entry(item)
                ok, status, freed = self.deleter.delete_entry(entry, self.deletion_mode)

                if ok:
                    self.deleted_items.append(item)
                    self.freed_bytes += freed
                    deleted_count += 1
                    print(f"  [OK] {status}: {item.name} ({_human_bytes(item.size)})")
                else:
                    print(f"  [SKIP] {item.name}: {status}")
            except Exception as e:
                print(f"  [ERR] Failed to delete {item.name}: {e}")

        return deleted_count
    
    def generate_report(self) -> str:
        """Generate cleanup report."""
        lines = [
            "=" * 60,
            " SAFE CLEANUP REPORT",
            "=" * 60,
            "",
            f"Total items scanned: {len(self.cleanup_items)}",
            f"Approved for deletion: {len(self.approved_items)}",
            f"Denied deletion: {len(self.denied_items)}",
            f"Actually deleted: {len(self.deleted_items)}",
            f"Freed space: {_human_bytes(self.freed_bytes)}",
            "",
            "Items by category:",
            "-" * 40,
        ]
        
        categories = {}
        for item in self.cleanup_items:
            categories.setdefault(item.category, []).append(item)
        
        for category, items in categories.items():
            total_size = sum(item.size for item in items)
            lines.append(f"  {category:15s}: {len(items):5d} items ({_human_bytes(total_size)})")
        
        return "\n".join(lines)
