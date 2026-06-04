"""Iterative Scanner - Learns from user feedback.

Key improvements:
1. Second/third scan drills deeper automatically
2. Remembers what user deleted before
3. Shows file-level details when needed
4. Suggests cleanup based on patterns
"""
from __future__ import annotations
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

import logging
from .types import _human_bytes
from .scanner_v3 import DeepScanner, ScanItem

log = logging.getLogger(__name__)


@dataclass
class CleanupHistory:
    """Tracks what user deleted before."""
    path: str
    size: int
    deleted_at: str
    category: str


class IterativeScanner:
    """Scanner that learns and improves with each scan."""
    
    HISTORY_FILE = Path.home() / '.cache' / 'storage-analyzer' / 'cleanup_history.json'
    
    def __init__(self):
        self.history: list[CleanupHistory] = []
        self.load_history()
        self.scan_count = 0
    
    def load_history(self):
        """Load cleanup history."""
        if self.HISTORY_FILE.exists():
            try:
                data = json.loads(self.HISTORY_FILE.read_text())
                self.history = [CleanupHistory(**h) for h in data]
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Could not load cleanup history: %s", e)
                self.history = []
    
    def save_history(self):
        """Save cleanup history."""
        self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [{'path': h.path, 'size': h.size, 'deleted_at': h.deleted_at, 'category': h.category}
                for h in self.history]
        try:
            self.HISTORY_FILE.write_text(json.dumps(data, indent=2))
        except OSError as e:
            log.warning("Could not save cleanup history: %s", e)
    
    def record_cleanup(self, path: str, size: int, category: str):
        """Record a cleanup action."""
        self.history.append(CleanupHistory(
            path=path,
            size=size,
            deleted_at=datetime.now().isoformat(),
            category=category,
        ))
        self.save_history()
    
    def scan_with_learning(self, path: str | Path, user_feedback: dict = None) -> ScanItem:
        """Scan with learning from previous feedback."""
        self.scan_count += 1
        
        # Determine depth based on scan count
        if self.scan_count == 1:
            max_depth = 2  # First scan: shallow
            min_size = 50 * 1024 * 1024  # 50MB
        elif self.scan_count == 2:
            max_depth = 3  # Second scan: deeper
            min_size = 10 * 1024 * 1024  # 10MB
        else:
            max_depth = 4  # Third+: full depth
            min_size = 1 * 1024 * 1024  # 1MB
        
        # Adjust based on user feedback
        if user_feedback:
            if user_feedback.get('want_deeper'):
                max_depth += 1
            if user_feedback.get('want_smaller'):
                min_size = min_size // 2
        
        # Run scan
        scanner = DeepScanner(max_depth=max_depth, min_size=min_size)
        result = scanner.scan(path)
        
        # Mark previously deleted items
        self._mark_deleted(result)
        
        return result
    
    def _mark_deleted(self, item: ScanItem):
        """Mark items that were previously deleted."""
        for h in self.history:
            if str(item.path) == h.path:
                item.reason = f'Previously deleted ({h.deleted_at[:10]})'
                break
        for child in item.children:
            self._mark_deleted(child)
    
    def get_suggestions(self, item: ScanItem) -> list[dict]:
        """Get cleanup suggestions based on patterns."""
        suggestions = []
        
        # Suggest based on history
        if self.history:
            # Find similar items that were deleted
            deleted_categories = set(h.category for h in self.history)
            for child in item.children:
                if child.category in deleted_categories:
                    suggestions.append({
                        'item': child,
                        'reason': f'You deleted similar {child.category} items before',
                        'confidence': 0.8,
                    })
        
        # Suggest based on size
        for child in item.children:
            if child.size > 1 * 1024**3:  # >1GB
                suggestions.append({
                    'item': child,
                    'reason': 'Large item (>1GB)',
                    'confidence': 0.5,
                })
        
        return suggestions
    
    def interactive_drill(self, item: ScanItem, depth: int = 0):
        """Interactive drill-down - user can explore any item."""
        if depth > 3:
            return
        
        print(f"\n{'  ' * depth}📁 {item.name} ({_human_bytes(item.size)})")
        
        if not item.children:
            return
        
        # Show children
        for i, child in enumerate(item.children[:10]):
            icon = '📁' if child.is_dir else '📄'
            cat_icon = {'SAFE': '🟢', 'REVIEW': '🟡', 'KEEP': '🔴'}.get(child.category, '⚪')
            print(f"{'  ' * (depth+1)}{i+1}. {icon} {child.name:<30s} {_human_bytes(child.size):>10s} {cat_icon}")
        
        # Ask user
        print(f"\n{'  ' * depth}Options:")
        print(f"{'  ' * depth}  1-{min(10, len(item.children))}: Drill into item")
        print(f"{'  ' * depth}  0: Back")
        
        try:
            choice = input(f"{'  ' * depth}Choice: ").strip()
            if choice == '0':
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(item.children):
                self.interactive_drill(item.children[idx], depth + 1)
        except (ValueError, IndexError):
            pass


# Example usage
if __name__ == '__main__':
    scanner = IterativeScanner()
    
    print("First scan (shallow)...")
    result = scanner.scan_with_learning(r'D:\ASUS')
    print(f"Found {len(result.children)} items")
    
    print("\nSecond scan (deeper)...")
    result = scanner.scan_with_learning(r'D:\ASUS')
    print(f"Found {len(result.children)} items")
