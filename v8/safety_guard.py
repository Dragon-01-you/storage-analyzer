"""Safety Guard - Absolute safety mechanism.

This module ensures:
1. NEVER delete user software without explicit confirmation
2. ALWAYS ask before deleting anything
3. Maintain a whitelist of protected applications
4. Log all deletion attempts for audit
"""
from __future__ import annotations
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .types import _human_bytes


@dataclass
class ProtectedItem:
    """A protected item that cannot be deleted without explicit confirmation."""
    path: str
    name: str
    category: str  # SOFTWARE, DOCUMENT, MEDIA, etc.
    reason: str
    added_at: str
    added_by: str  # USER, SYSTEM, AUTO


@dataclass
class DeletionRequest:
    """A request to delete an item."""
    path: str
    name: str
    size: int
    category: str
    reason: str
    requested_at: str
    approved: bool = False
    approved_by: str = ""
    approved_at: str = ""


class SafetyGuard:
    """Absolute safety mechanism for deletion operations."""
    
    # Protected paths - NEVER delete these without explicit confirmation
    PROTECTED_PATHS = {
        # User software
        'Trae CN': 'Trae CN IDE',
        'BcutBilibili': 'Bilibili Video Editor',
        'Quark': 'Quark Browser',
        'JianyingPro': 'Jianying Video Editor',
        'cursor': 'Cursor IDE',
        'opencode': 'OpenCode IDE',
        'VS Code': 'Visual Studio Code',
        
        # User data
        'Documents': 'User Documents',
        'Downloads': 'User Downloads',
        'Desktop': 'User Desktop',
        'Pictures': 'User Pictures',
        'Videos': 'User Videos',
        'Music': 'User Music',
        
        # Important directories
        'OneDrive': 'OneDrive Sync',
        'Google Drive': 'Google Drive',
        'Dropbox': 'Dropbox',
        
        # Development tools
        'node_modules': 'Node.js Dependencies',
        '.git': 'Git Repository',
        '.venv': 'Python Virtual Environment',
        'venv': 'Python Virtual Environment',
        
        # System directories
        'Windows': 'Windows System',
        'Program Files': 'Installed Programs',
        'Program Files (x86)': 'Installed Programs (x86)',
        'AppData': 'Application Data',
    }
    
    # Protected extensions - NEVER delete these without confirmation
    PROTECTED_EXTENSIONS = {
        '.exe': 'Executable',
        '.msi': 'Installer',
        '.zip': 'Archive',
        '.rar': 'Archive',
        '.7z': 'Archive',
        '.iso': 'Disk Image',
        '.dmg': 'Disk Image',
        '.app': 'Application',
        '.lnk': 'Shortcut',
    }
    
    def __init__(self):
        self.protected_items: list[ProtectedItem] = []
        self.deletion_log: list[DeletionRequest] = []
        self.load_protected_items()
    
    def load_protected_items(self):
        """Load protected items from file."""
        config_path = Path.home() / '.cache' / 'storage-analyzer' / 'protected_items.json'
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                self.protected_items = [ProtectedItem(**item) for item in data]
            except (json.JSONDecodeError, OSError, TypeError):
                self.protected_items = []
    
    def save_protected_items(self):
        """Save protected items to file."""
        config_path = Path.home() / '.cache' / 'storage-analyzer' / 'protected_items.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = [{'path': item.path, 'name': item.name, 'category': item.category, 
                 'reason': item.reason, 'added_at': item.added_at, 'added_by': item.added_by}
                for item in self.protected_items]
        config_path.write_text(json.dumps(data, indent=2))
    
    def is_protected(self, path: str) -> tuple[bool, str]:
        """Check if a path is protected."""
        path_lower = path.lower()
        
        # Check protected paths
        for protected_name, reason in self.PROTECTED_PATHS.items():
            if protected_name.lower() in path_lower:
                return True, f"Protected: {reason}"
        
        # Check protected extensions
        ext = Path(path).suffix.lower()
        if ext in self.PROTECTED_EXTENSIONS:
            return True, f"Protected extension: {self.PROTECTED_EXTENSIONS[ext]}"
        
        # Check custom protected items
        for item in self.protected_items:
            if item.path.lower() in path_lower:
                return True, f"User protected: {item.reason}"
        
        return False, ""
    
    def request_deletion(self, path: str, name: str, size: int, category: str, reason: str) -> DeletionRequest:
        """Request deletion of an item."""
        request = DeletionRequest(
            path=path,
            name=name,
            size=size,
            category=category,
            reason=reason,
            requested_at=datetime.now().isoformat(),
        )
        
        # Check if protected
        is_protected, protection_reason = self.is_protected(path)
        if is_protected:
            request.approved = False
            request.approved_by = "SYSTEM"
            request.approved_at = datetime.now().isoformat()
            print(f"  ⚠️ BLOCKED: {name} - {protection_reason}")
            return request
        
        # Log the request
        self.deletion_log.append(request)
        return request
    
    def approve_deletion(self, request: DeletionRequest, approved_by: str = "USER") -> bool:
        """Approve a deletion request."""
        request.approved = True
        request.approved_by = approved_by
        request.approved_at = datetime.now().isoformat()
        return True
    
    def deny_deletion(self, request: DeletionRequest, denied_by: str = "USER") -> bool:
        """Deny a deletion request."""
        request.approved = False
        request.approved_by = denied_by
        request.approved_at = datetime.now().isoformat()
        return False
    
    def add_protected_item(self, path: str, name: str, category: str, reason: str, added_by: str = "USER"):
        """Add a new protected item."""
        item = ProtectedItem(
            path=path,
            name=name,
            category=category,
            reason=reason,
            added_at=datetime.now().isoformat(),
            added_by=added_by,
        )
        self.protected_items.append(item)
        self.save_protected_items()
    
    def remove_protected_item(self, path: str):
        """Remove a protected item."""
        self.protected_items = [item for item in self.protected_items if item.path != path]
        self.save_protected_items()
    
    def get_deletion_log(self) -> list[DeletionRequest]:
        """Get the deletion log."""
        return self.deletion_log
    
    def save_deletion_log(self):
        """Save deletion log to file."""
        log_path = Path.home() / '.cache' / 'storage-analyzer' / 'deletion_log.json'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        data = [{'path': req.path, 'name': req.name, 'size': req.size,
                 'category': req.category, 'reason': req.reason,
                 'requested_at': req.requested_at, 'approved': req.approved,
                 'approved_by': req.approved_by, 'approved_at': req.approved_at}
                for req in self.deletion_log]
        log_path.write_text(json.dumps(data, indent=2))
    
    def generate_report(self) -> str:
        """Generate a safety report."""
        lines = [
            "=" * 60,
            " SAFETY GUARD REPORT",
            "=" * 60,
            "",
            f"Protected Items: {len(self.protected_items)}",
            f"Deletion Requests: {len(self.deletion_log)}",
            "",
            "Protected Paths:",
            "-" * 40,
        ]
        
        for name, reason in list(self.PROTECTED_PATHS.items())[:10]:
            lines.append(f"  {name:20s}: {reason}")
        
        lines.append("")
        lines.append("Protected Extensions:")
        lines.append("-" * 40)
        
        for ext, reason in list(self.PROTECTED_EXTENSIONS.items())[:10]:
            lines.append(f"  {ext:10s}: {reason}")
        
        return "\n".join(lines)
