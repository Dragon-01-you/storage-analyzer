"""4-tier confidence system for file cleanup decisions.

Inspired by DiskPilot's confidence tiers:
- SAFE: Definitely deletable (temp, cache, logs)
- RECOMMENDED: Very likely safe (old installers, duplicates)
- SUGGESTED: Probably fine, worth a glance (stale archives)
- ASK: Only you know (old media, abandoned projects)

This system provides more granular control than simple risk levels.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path


class ConfidenceTier(Enum):
    """Confidence tiers for cleanup decisions."""
    SAFE = "safe"           # Definitely deletable
    RECOMMENDED = "recommended"  # Very likely safe
    SUGGESTED = "suggested"     # Probably fine, worth a glance
    ASK = "ask"             # Only you know


@dataclass
class TieredEntry:
    """An entry with confidence tier."""
    path: str
    name: str
    size_bytes: int
    tier: ConfidenceTier
    reason: str
    category: str
    details: Dict[str, Any] = None

    @property
    def size_human(self) -> str:
        """Human-readable size."""
        from .types import _human_bytes
        return _human_bytes(self.size_bytes)

    @property
    def tier_emoji(self) -> str:
        """Emoji for tier."""
        return {
            ConfidenceTier.SAFE: "[SAFE]",
            ConfidenceTier.RECOMMENDED: "[REC]",
            ConfidenceTier.SUGGESTED: "[SUG]",
            ConfidenceTier.ASK: "[ASK]",
        }[self.tier]

    @property
    def tier_color(self) -> str:
        """Color for tier (ANSI)."""
        return {
            ConfidenceTier.SAFE: "\033[92m",      # Green
            ConfidenceTier.RECOMMENDED: "\033[94m", # Blue
            ConfidenceTier.SUGGESTED: "\033[93m",   # Yellow
            ConfidenceTier.ASK: "\033[91m",         # Red
        }[self.tier]


class ConfidenceAnalyzer:
    """Analyze files and assign confidence tiers.

    Tier assignment rules:
    1. SAFE: Known safe patterns (temp, cache, logs, crash dumps)
    2. RECOMMENDED: Likely safe (old files, duplicates, installers)
    3. SUGGESTED: Needs review (archives, backups, media)
    4. ASK: Unknown or high-risk (user data, applications)
    """

    # SAFE patterns (definitely deletable)
    SAFE_PATTERNS = [
        # Temp files
        (r'\.tmp$', 'Temporary file'),
        (r'\.temp$', 'Temporary file'),
        (r'~$', 'Backup file'),
        (r'\.bak$', 'Backup file'),
        (r'\.orig$', 'Original backup'),
        # Cache directories
        (r'[\\/]cache[\\/]', 'Cache directory'),
        (r'[\\/]Cache[\\/]', 'Cache directory'),
        (r'\.cache', 'Cache file'),
        # Log files
        (r'\.log$', 'Log file'),
        (r'\.log\.\d+$', 'Rotated log'),
        # Crash dumps
        (r'\.dmp$', 'Crash dump'),
        (r'\.mdmp$', 'Minidump'),
        (r'\.hdmp$', 'Heap dump'),
        # Thumbnails
        (r'Thumbs\.db$', 'Thumbnail cache'),
        (r'\.DS_Store$', 'macOS metadata'),
        # Browser cache
        (r'[\\/]GPUCache[\\/]', 'GPU cache'),
        (r'[\\/]Code Cache[\\/]', 'Code cache'),
        # Python
        (r'__pycache__', 'Python bytecode'),
        (r'\.pyc$', 'Python compiled'),
        # Node
        (r'node_modules', 'Node dependencies'),
        # Windows
        (r'[\\/]Temp[\\/]', 'Windows temp'),
        (r'[\\/]Prefetch[\\/]', 'Prefetch cache'),
    ]

    # RECOMMENDED patterns (very likely safe)
    RECOMMENDED_PATTERNS = [
        # Old files (>180 days)
        # Duplicates
        # Old installers
        (r'\.iso$', 'Disk image'),
        (r'\.dmg$', 'macOS disk image'),
        (r'\.msi$', 'Windows installer'),
        (r'\.exe$', 'Executable'),
    ]

    # SUGGESTED patterns (needs review)
    SUGGESTED_PATTERNS = [
        # Archives
        (r'\.zip$', 'ZIP archive'),
        (r'\.rar$', 'RAR archive'),
        (r'\.7z$', '7-Zip archive'),
        (r'\.tar$', 'TAR archive'),
        (r'\.gz$', 'Gzip archive'),
        # Backups
        (r'\.backup$', 'Backup file'),
        (r'\.old$', 'Old file'),
    ]

    # ASK patterns (high risk - user data)
    ASK_PATTERNS = [
        # User data
        (r'\.docx?$', 'Word document'),
        (r'\.xlsx?$', 'Excel spreadsheet'),
        (r'\.pptx?$', 'PowerPoint'),
        (r'\.pdf$', 'PDF document'),
        (r'\.txt$', 'Text file'),
        (r'\.md$', 'Markdown file'),
        # Media
        (r'\.jpg$', 'JPEG image'),
        (r'\.png$', 'PNG image'),
        (r'\.mp4$', 'MP4 video'),
        (r'\.mp3$', 'MP3 audio'),
    ]

    def __init__(self, min_age_days: int = 180) -> None:
        self.min_age_days = min_age_days

    def analyze(self, path: str, size_bytes: int, mtime: float = None) -> TieredEntry:
        """Analyze a file and assign a confidence tier."""
        import re
        from pathlib import Path

        p = Path(path)
        name = p.name
        now = time.time()
        age_days = (now - mtime) / 86400 if mtime else 0

        # Check SAFE patterns
        for pattern, reason in self.SAFE_PATTERNS:
            if re.search(pattern, str(p), re.IGNORECASE):
                return TieredEntry(
                    path=str(p),
                    name=name,
                    size_bytes=size_bytes,
                    tier=ConfidenceTier.SAFE,
                    reason=reason,
                    category='safe',
                )

        # Check RECOMMENDED patterns (with age check)
        for pattern, reason in self.RECOMMENDED_PATTERNS:
            if re.search(pattern, str(p), re.IGNORECASE):
                if age_days > self.min_age_days:
                    return TieredEntry(
                        path=str(p),
                        name=name,
                        size_bytes=size_bytes,
                        tier=ConfidenceTier.RECOMMENDED,
                        reason=f"{reason} (>{self.min_age_days} days old)",
                        category='recommended',
                    )
                else:
                    return TieredEntry(
                        path=str(p),
                        name=name,
                        size_bytes=size_bytes,
                        tier=ConfidenceTier.SUGGESTED,
                        reason=reason,
                        category='suggested',
                    )

        # Check SUGGESTED patterns
        for pattern, reason in self.SUGGESTED_PATTERNS:
            if re.search(pattern, str(p), re.IGNORECASE):
                return TieredEntry(
                    path=str(p),
                    name=name,
                    size_bytes=size_bytes,
                    tier=ConfidenceTier.SUGGESTED,
                    reason=reason,
                    category='suggested',
                )

        # Check ASK patterns
        for pattern, reason in self.ASK_PATTERNS:
            if re.search(pattern, str(p), re.IGNORECASE):
                return TieredEntry(
                    path=str(p),
                    name=name,
                    size_bytes=size_bytes,
                    tier=ConfidenceTier.ASK,
                    reason=reason,
                    category='ask',
                )

        # Default: ASK (unknown)
        return TieredEntry(
            path=str(p),
            name=name,
            size_bytes=size_bytes,
            tier=ConfidenceTier.ASK,
            reason="Unknown file type",
            category='unknown',
        )

    def analyze_directory(self, dir_path: str) -> List[TieredEntry]:
        """Analyze all files in a directory."""
        entries = []
        try:
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp)
                        entry = self.analyze(fp, st.st_size, st.st_mtime)
                        entries.append(entry)
                    except OSError:
                        continue
        except OSError:
            pass
        return entries

    def get_summary(self, entries: List[TieredEntry]) -> Dict[str, Any]:
        """Get summary of tiered entries."""
        summary = {
            'total': len(entries),
            'tiers': {
                'safe': {'count': 0, 'bytes': 0},
                'recommended': {'count': 0, 'bytes': 0},
                'suggested': {'count': 0, 'bytes': 0},
                'ask': {'count': 0, 'bytes': 0},
            },
        }
        for entry in entries:
            tier = entry.tier.value
            summary['tiers'][tier]['count'] += 1
            summary['tiers'][tier]['bytes'] += entry.size_bytes
        return summary


class PiracyDetector:
    """Detect piracy-related files.

    Inspired by DiskPilot's piracy detection.
    """

    # Known piracy patterns
    PIRACY_PATTERNS = [
        # Keygens
        (r'(?i)keygen', 'Key generator'),
        (r'(?i)kg\.exe', 'Key generator'),
        (r'(?i)crack', 'Crack'),
        (r'(?i)patch\.exe', 'Patch executable'),
        (r'(?i)activator', 'Activator'),
        (r'(?i)loader\.exe', 'Loader'),
        # Common piracy tools
        (r'(?i)amtlib\.dll', 'Adobe crack'),
        (r'(?i)universal.*patch', 'Universal patch'),
        # Serial/key files
        (r'(?i)serial\.txt', 'Serial number'),
        (r'(?i)license\.key', 'License key'),
        (r'(?i)crack\.txt', 'Crack instructions'),
    ]

    def detect(self, path: str) -> Optional[TieredEntry]:
        """Detect if a file is piracy-related."""
        import re
        from pathlib import Path

        p = Path(path)
        name = p.name

        for pattern, reason in self.PIRACY_PATTERNS:
            if re.search(pattern, name):
                try:
                    st = os.stat(path)
                    return TieredEntry(
                        path=str(p),
                        name=name,
                        size_bytes=st.st_size,
                        tier=ConfidenceTier.ASK,
                        reason=f"[SECURITY] {reason}",
                        category='piracy',
                        details={'risk': 'security'},
                    )
                except OSError:
                    continue
        return None


class VersionDetector:
    """Detect old versions of installers.

    Inspired by DiskPilot's version detection.
    """

    def detect_old_versions(self, directory: str) -> List[TieredEntry]:
        """Find old versions of installers in a directory."""
        import re
        from collections import defaultdict

        # Group files by base name (without version)
        version_groups = defaultdict(list)

        try:
            for f in os.listdir(directory):
                fp = os.path.join(directory, f)
                if not os.path.isfile(fp):
                    continue

                # Extract base name and version
                base, version = self._extract_version(f)
                if base and version:
                    try:
                        st = os.stat(fp)
                        version_groups[base].append({
                            'path': fp,
                            'name': f,
                            'version': version,
                            'mtime': st.st_mtime,
                            'size': st.st_size,
                        })
                    except OSError:
                        continue
        except OSError:
            pass

        # Find old versions
        old_versions = []
        for base, versions in version_groups.items():
            if len(versions) < 2:
                continue

            # Sort by version (newest first)
            versions.sort(key=lambda x: x['version'], reverse=True)

            # Mark older versions
            for v in versions[1:]:
                old_versions.append(TieredEntry(
                    path=v['path'],
                    name=v['name'],
                    size_bytes=v['size'],
                    tier=ConfidenceTier.RECOMMENDED,
                    reason=f"Old version of {base} (newer: {versions[0]['version']})",
                    category='old_version',
                ))

        return old_versions

    def _extract_version(self, filename: str) -> tuple:
        """Extract base name and version from filename."""
        import re

        # Common version patterns
        patterns = [
            # setup_v1.2.3.exe, app-1.2.3.exe
            (r'^(.+?)[-_]v?(\d+\.\d+\.\d+).*\.(exe|msi|dmg)$', 2),
            # app123.exe (no dots)
            (r'^(.+?)(\d{3,})\.(exe|msi|dmg)$', 2),
        ]

        for pattern, group_idx in patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                base = match.group(1).rstrip('-_')
                version = match.group(group_idx)
                return base, version

        return None, None
