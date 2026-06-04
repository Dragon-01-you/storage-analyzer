"""Scanner v3 - Deep recursive scanner with user-guided cleanup.

Key improvements over v2:
1. Recursive scanning with depth control
2. Smart categorization for each item
3. User can drill into any item
4. Shows what's safe to delete
5. Handles large directories efficiently
"""
from __future__ import annotations
import os
import sys
import shutil
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from .types import (
    _human_bytes, CleanEntry, DirectorySummary, CognitiveLabel,
    RiskLevel, LabelSource, DeletionMode,
)
import logging
from .safeguard import ProtectedPaths, SafeDeleter

log = logging.getLogger(__name__)


@dataclass
class ScanItem:
    """A single scanned item."""
    path: Path
    name: str
    size: int
    file_count: int
    is_dir: bool
    depth: int
    category: str  # SAFE, REVIEW, KEEP, UNKNOWN
    reason: str
    children: list['ScanItem']
    last_modified: Optional[datetime] = None


class DeepScanner:
    """Recursive scanner with smart categorization."""
    
    # Safe to delete patterns
    SAFE_PATTERNS = {
        'cache': 'Cache files',
        'temp': 'Temporary files',
        'tmp': 'Temporary files',
        'log': 'Log files',
        'crashdump': 'Crash dumps',
        'node_modules': 'Node.js deps (reinstallable)',
        '__pycache__': 'Python bytecode',
        '.next': 'Next.js cache',
        'shader_cache': 'Shader cache',
        'htmlcache': 'HTML cache',
        'webcache': 'Web cache',
        'thumbnail': 'Thumbnails',
        'iconcache': 'Icon cache',
        'prefetch': 'Prefetch files',
    }
    
    # Keep patterns
    KEEP_PATTERNS = {
        'vmware': 'VMware VM',
        '.vmdk': 'VM disk',
        '.vmx': 'VM config',
        'ubuntu': 'Ubuntu VM',
        'wsl': 'WSL',
        '.vhdx': 'Virtual disk',
        'onedrive': 'Cloud sync',
        'dropbox': 'Cloud sync',
        'program files': 'Installed programs',
        'windows': 'System',
        '.git': 'Git repo',
    }
    
    # Review patterns
    REVIEW_PATTERNS = {
        'download': 'Downloads',
        '下载': 'Downloads',
        'installer': 'Installer',
        'setup': 'Setup file',
        'backup': 'Backup',
        'bak': 'Backup',
        'old': 'Old files',
        'iso': 'Disk image',
        'video': 'Video',
        'movie': 'Movie',
        'photo': 'Photo',
    }
    
    def __init__(self, max_depth: int = 4, min_size: int = 10 * 1024 * 1024):
        """Initialize scanner.
        
        Args:
            max_depth: Maximum recursion depth
            min_size: Minimum size to report (default 10MB)
        """
        self.max_depth = max_depth
        self.min_size = min_size
        self.stats = {
            'total_scanned': 0,
            'total_size': 0,
            'safe_size': 0,
            'review_size': 0,
            'keep_size': 0,
        }
    
    def scan(self, path: str | Path) -> ScanItem:
        """Scan a directory recursively."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        return self._scan_item(p, depth=0)
    
    def _scan_item(self, path: Path, depth: int) -> ScanItem:
        """Recursively scan an item."""
        self.stats['total_scanned'] += 1
        
        try:
            is_dir = path.is_dir()
            
            if is_dir:
                size, count, children = self._scan_dir(path, depth)
            else:
                size = path.stat().st_size
                count = 1
                children = []
            
            self.stats['total_size'] += size
            
            # Categorize
            category, reason = self._categorize(path, size, is_dir)
            
            if category == 'SAFE':
                self.stats['safe_size'] += size
            elif category == 'REVIEW':
                self.stats['review_size'] += size
            else:
                self.stats['keep_size'] += size
            
            # Get last modified
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                mtime = None
            
            return ScanItem(
                path=path,
                name=path.name,
                size=size,
                file_count=count,
                is_dir=is_dir,
                depth=depth,
                category=category,
                reason=reason,
                children=children,
                last_modified=mtime,
            )
        except (PermissionError, OSError) as e:
            return ScanItem(
                path=path,
                name=path.name,
                size=0,
                file_count=0,
                is_dir=path.is_dir(),
                depth=depth,
                category='UNKNOWN',
                reason=f'Error: {e}',
                children=[],
            )
    
    def _scan_dir(self, path: Path, depth: int) -> tuple[int, int, list[ScanItem]]:
        """Scan a directory."""
        if depth >= self.max_depth:
            # Don't recurse further, just count
            return self._quick_dir_size(path)
        
        total_size = 0
        total_count = 0
        children = []
        
        try:
            for item in path.iterdir():
                try:
                    child = self._scan_item(item, depth + 1)
                    if child.size >= self.min_size:
                        children.append(child)
                    total_size += child.size
                    total_count += child.file_count
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass
        
        children.sort(key=lambda x: -x.size)
        return total_size, total_count, children
    
    def _quick_dir_size(self, path: Path) -> tuple[int, int, list[ScanItem]]:
        """Quick size calculation without recursion."""
        total = 0
        count = 0
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += (Path(root) / f).stat().st_size
                        count += 1
                    except OSError:
                        pass
        except OSError:
            pass
        return total, count, []
    
    def _categorize(self, path: Path, size: int, is_dir: bool) -> tuple[str, str]:
        """Categorize an item."""
        name = path.name.lower()
        path_str = str(path).lower()
        
        # SAFE
        for pattern, reason in self.SAFE_PATTERNS.items():
            if pattern in name or pattern in path_str:
                return 'SAFE', reason
        
        # KEEP
        for pattern, reason in self.KEEP_PATTERNS.items():
            if pattern in name or pattern in path_str:
                return 'KEEP', reason
        
        # REVIEW
        for pattern, reason in self.REVIEW_PATTERNS.items():
            if pattern in name or pattern in path_str:
                return 'REVIEW', reason
        
        # Large unknown
        if size > 500 * 1024 * 1024:
            return 'REVIEW', 'Large unknown'
        
        # Small
        return 'REVIEW', 'Unknown small item'
    
    def print_tree(self, item: ScanItem, prefix: str = "", is_last: bool = True, max_depth: int = 3):
        """Print tree structure."""
        if item.depth > max_depth:
            return
        
        connector = "└── " if is_last else "├── "
        size_str = _human_bytes(item.size)
        
        icon_map = {'SAFE': '🟢', 'REVIEW': '🟡', 'KEEP': '🔴', 'UNKNOWN': '⚪'}
        icon = icon_map.get(item.category, '⚪')
        
        if item.is_dir:
            print(f"{prefix}{connector}📁 {item.name:<35s} {size_str:>10s} {icon} [{item.category}]")
            if item.children:
                extension = "    " if is_last else "│   "
                for i, child in enumerate(item.children):
                    self.print_tree(child, prefix + extension, i == len(item.children) - 1, max_depth)
        else:
            print(f"{prefix}{connector}📄 {item.name:<35s} {size_str:>10s} {icon} [{item.category}]")
    
    def collect_by_category(self, item: ScanItem, category: str) -> list[ScanItem]:
        """Collect all items of a category."""
        result = []
        if item.category == category:
            result.append(item)
        for child in item.children:
            result.extend(self.collect_by_category(child, category))
        return result
    
    def get_summary(self) -> dict:
        """Get scan summary."""
        return {
            'total_scanned': self.stats['total_scanned'],
            'total_size': self.stats['total_size'],
            'safe_size': self.stats['safe_size'],
            'review_size': self.stats['review_size'],
            'keep_size': self.stats['keep_size'],
        }


class CleanupEngine:
    """User-guided cleanup engine with SafeDeleter integration."""

    def __init__(self, scanner: DeepScanner, deletion_mode: DeletionMode = DeletionMode.DRY_RUN):
        self.scanner = scanner
        self.freed = 0
        self.errors = 0
        self.protected = ProtectedPaths()
        self.deleter = SafeDeleter(self.protected)
        self.deletion_mode = deletion_mode

    def _item_to_entry(self, item: ScanItem) -> CleanEntry:
        """Convert a ScanItem to a CleanEntry for SafeDeleter."""
        summary = DirectorySummary(
            path=item.path,
            total_bytes=item.size,
            file_count=item.file_count,
            last_modified=item.last_modified,
        )
        # Map scanner category to risk level
        risk_map = {
            'SAFE': RiskLevel.LOW,
            'REVIEW': RiskLevel.MEDIUM,
            'KEEP': RiskLevel.HIGH,
            'UNKNOWN': RiskLevel.MEDIUM,
        }
        risk = risk_map.get(item.category, RiskLevel.MEDIUM)
        label = CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label=item.reason,
            human_readable_risk=f"Category: {item.category}",
            confidence=0.8,
            technical_name=item.name,
            technical_path=str(item.path),
        )
        # Stable id from path
        entry_id = hex(hash(str(item.path)) & 0xFFFFFFFF)[2:]
        return CleanEntry(id=entry_id, summary=summary, label=label, risk_level=risk)

    def delete_item(self, item: ScanItem) -> tuple[bool, str]:
        """Delete a single item via SafeDeleter (respects protected paths)."""
        if self.protected.is_protected(item.path):
            return False, "protected path — skipped"
        entry = self._item_to_entry(item)
        ok, msg, bytes_freed = self.deleter.delete_entry(entry, self.deletion_mode)
        if ok:
            self.freed += bytes_freed
        else:
            self.errors += 1
        return ok, msg

    def delete_safe_items(self, root: ScanItem, confirm: bool = False) -> int:
        """Delete all SAFE items. Requires confirm=True to actually delete."""
        safe_items = self.scanner.collect_by_category(root, 'SAFE')
        total_size = sum(i.size for i in safe_items)

        log.info("SAFE items to delete (%d items, %s):", len(safe_items), _human_bytes(total_size))
        for i, item in enumerate(safe_items[:20]):
            log.info("  %d. %-30s %10s  (%s)", i + 1, item.name, _human_bytes(item.size), item.reason)
        if len(safe_items) > 20:
            log.info("  ... and %d more", len(safe_items) - 20)

        if not confirm:
            log.info("[DRY RUN] Pass confirm=True to actually delete.")
            return 0

        deleted = 0
        for item in safe_items:
            ok, msg = self.delete_item(item)
            if ok:
                deleted += 1
            else:
                log.info("[SKIP] %s: %s", item.name, msg)

        return deleted
    
    def interactive_cleanup(self, root: ScanItem):
        """Interactive cleanup - user decides each item."""
        print("\n" + "=" * 60)
        print(" INTERACTIVE CLEANUP")
        print("=" * 60)
        
        # Show categories
        safe_items = self.scanner.collect_by_category(root, 'SAFE')
        review_items = self.scanner.collect_by_category(root, 'REVIEW')
        
        safe_size = sum(i.size for i in safe_items)
        review_size = sum(i.size for i in review_items)
        
        print(f"\n🟢 SAFE to delete ({_human_bytes(safe_size)}):")
        for i, item in enumerate(safe_items[:10]):
            print(f"  {i+1}. {item.name:<30s} {_human_bytes(item.size):>10s}  ({item.reason})")
        
        print(f"\n🟡 REVIEW needed ({_human_bytes(review_size)}):")
        for i, item in enumerate(review_items[:10]):
            print(f"  {i+1}. {item.name:<30s} {_human_bytes(item.size):>10s}  ({item.reason})")
        
        # Ask what to delete
        print("\nOptions:")
        print("  1. Delete all SAFE items")
        print("  2. Delete specific items")
        print("  3. Skip")
        
        choice = input("\nYour choice (1/2/3): ").strip()
        
        if choice == '1':
            deleted = self.delete_safe_items(root, confirm=True)
            print(f"\nDeleted {deleted} items, freed {_human_bytes(self.freed)}")
        elif choice == '2':
            # Show all items for selection
            all_items = safe_items + review_items
            print("\nSelect items to delete (comma-separated numbers):")
            for i, item in enumerate(all_items):
                cat_icon = '🟢' if item.category == 'SAFE' else '🟡'
                print(f"  {i+1}. {cat_icon} {item.name:<30s} {_human_bytes(item.size):>10s}")
            
            selections = input("\nNumbers: ").strip().split(',')
            for sel in selections:
                try:
                    idx = int(sel.strip()) - 1
                    if 0 <= idx < len(all_items):
                        ok, msg = self.delete_item(all_items[idx])
                        if ok:
                            log.info("[OK] %s", all_items[idx].name)
                        else:
                            log.info("[SKIP] %s: %s", all_items[idx].name, msg)
                except (ValueError, IndexError):
                    pass
            
            print(f"\nFreed: {_human_bytes(self.freed)}")
