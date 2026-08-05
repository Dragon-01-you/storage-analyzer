"""Similar file detection inspired by Czkawka.

Features:
- Similar images (different resolution, watermarks)
- Similar videos (visual similarity)
- Similar music (by tags or content)
- Corrupted file detection
- Wrong extension detection
"""
from __future__ import annotations
import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


@dataclass
class SimilarGroup:
    """A group of similar files."""
    files: List[str]
    similarity_type: str  # 'duplicate', 'similar_image', 'similar_video', 'similar_music'
    confidence: float  # 0.0 to 1.0
    wasted_bytes: int = 0

    @property
    def count(self) -> int:
        return len(self.files)


@dataclass
class CorruptedFile:
    """A corrupted or invalid file."""
    path: str
    reason: str
    size_bytes: int = 0


@dataclass
class WrongExtension:
    """A file with wrong extension."""
    path: str
    current_ext: str
    detected_ext: str
    confidence: float


class DuplicateFinder:
    """Find duplicate files using 3-stage pipeline.

    Stage 1: Group by file size
    Stage 2: Partial hash (first 64KB)
    Stage 3: Full SHA-256 hash
    """

    def __init__(self, min_size_bytes: int = 1024 * 1024) -> None:
        self.min_size = min_size_bytes

    def find_duplicates(self, paths: List[str]) -> List[SimilarGroup]:
        """Find duplicate files."""
        # Stage 1: Group by size
        size_groups = self._group_by_size(paths)
        if not size_groups:
            return []

        # Stage 2: Partial hash
        partial_groups = self._partial_hash(size_groups)
        if not partial_groups:
            return []

        # Stage 3: Full hash
        duplicates = self._full_hash(partial_groups)

        # Calculate wasted space
        for group in duplicates:
            if group.files:
                # Wasted = (count - 1) * file_size
                try:
                    size = os.path.getsize(group.files[0])
                    group.wasted_bytes = (group.count - 1) * size
                except OSError:
                    pass

        return duplicates

    def _group_by_size(self, paths: List[str]) -> Dict[int, List[str]]:
        """Group files by size."""
        size_groups = defaultdict(list)
        for path in paths:
            try:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            st = os.stat(fp)
                            if st.st_size >= self.min_size:
                                size_groups[st.st_size].append(fp)
                        except OSError:
                            continue
            except OSError:
                continue

        # Keep only groups with >1 file
        return {size: files for size, files in size_groups.items() if len(files) > 1}

    def _partial_hash(self, size_groups: Dict[int, List[str]]) -> Dict[str, List[str]]:
        """Compute partial hash (first 64KB)."""
        block_size = 65536  # 64KB
        partial_groups = defaultdict(list)

        for size, files in size_groups.items():
            for fp in files:
                h = self._hash_file_partial(fp, block_size)
                if h:
                    partial_groups[h].append(fp)

        # Keep only groups with >1 file
        return {h: files for h, files in partial_groups.items() if len(files) > 1}

    def _full_hash(self, partial_groups: Dict[str, List[str]]) -> List[SimilarGroup]:
        """Compute full SHA-256 hash."""
        duplicates = []

        for partial_hash, files in partial_groups.items():
            full_groups = defaultdict(list)

            for fp in files:
                h = self._hash_file_full(fp)
                if h:
                    full_groups[h].append(fp)

            for full_hash, group_files in full_groups.items():
                if len(group_files) > 1:
                    duplicates.append(SimilarGroup(
                        files=group_files,
                        similarity_type='duplicate',
                        confidence=1.0,
                    ))

        return duplicates

    def _hash_file_partial(self, path: str, block_size: int) -> Optional[str]:
        """Hash first N bytes of file."""
        try:
            with open(path, 'rb') as f:
                data = f.read(block_size)
                return hashlib.sha256(data).hexdigest()
        except OSError:
            return None

    def _hash_file_full(self, path: str) -> Optional[str]:
        """Hash entire file."""
        try:
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None


class CorruptedFileDetector:
    """Detect corrupted or invalid files.

    Checks:
    - Empty files that shouldn't be empty
    - Files that can't be read
    - Files with invalid content
    """

    # File types that should have content
    NON_EMPTY_TYPES = {
        '.exe', '.dll', '.sys', '.docx', '.xlsx', '.pptx',
        '.pdf', '.jpg', '.png', '.mp4', '.mp3', '.zip',
    }

    def detect(self, paths: List[str]) -> List[CorruptedFile]:
        """Detect corrupted files."""
        corrupted = []

        for path in paths:
            try:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        result = self._check_file(fp)
                        if result:
                            corrupted.append(result)
            except OSError:
                continue

        return corrupted

    def _check_file(self, path: str) -> Optional[CorruptedFile]:
        """Check if a file is corrupted."""
        try:
            st = os.stat(path)
            ext = os.path.splitext(path)[1].lower()

            # Check for empty files that shouldn't be empty
            if st.st_size == 0 and ext in self.NON_EMPTY_TYPES:
                return CorruptedFile(
                    path=path,
                    reason=f"Empty {ext} file",
                    size_bytes=0,
                )

            # Try to read first few bytes
            with open(path, 'rb') as f:
                header = f.read(16)
                if not header and st.st_size > 0:
                    return CorruptedFile(
                        path=path,
                        reason="File has size but can't be read",
                        size_bytes=st.st_size,
                    )

        except OSError as e:
            return CorruptedFile(
                path=path,
                reason=f"Can't read: {e}",
                size_bytes=0,
            )

        return None


class WrongExtensionDetector:
    """Detect files with wrong extensions.

    Uses magic bytes to detect actual file type.
    """

    # Magic bytes for common file types
    MAGIC_BYTES = {
        b'\x89PNG': '.png',
        b'\xff\xd8\xff': '.jpg',
        b'GIF8': '.gif',
        b'PK\x03\x04': '.zip',
        b'Rar!\x1a\x07': '.rar',
        b'\x37\x7a\xbc\xaf': '.7z',
        b'%PDF': '.pdf',
        b'MZ': '.exe',
        b'\x7fELF': '.elf',
        b'ID3': '.mp3',
        b'\xff\xfb': '.mp3',
        b'\xff\xf3': '.mp3',
        b'\x00\x00\x01\x00': '.ico',
        b'BM': '.bmp',
        b'RIFF': '.wav',  # or .avi
    }

    def detect(self, paths: List[str]) -> List[WrongExtension]:
        """Detect files with wrong extensions."""
        wrong_exts = []

        for path in paths:
            try:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(root, f)
                        result = self._check_extension(fp)
                        if result:
                            wrong_exts.append(result)
            except OSError:
                continue

        return wrong_exts

    def _check_extension(self, path: str) -> Optional[WrongExtension]:
        """Check if file has correct extension."""
        try:
            ext = os.path.splitext(path)[1].lower()
            if not ext:
                return None

            with open(path, 'rb') as f:
                header = f.read(16)

            for magic, detected_ext in self.MAGIC_BYTES.items():
                if header.startswith(magic):
                    if ext != detected_ext:
                        return WrongExtension(
                            path=path,
                            current_ext=ext,
                            detected_ext=detected_ext,
                            confidence=0.8,
                        )
                    break

        except OSError:
            pass

        return None


class SimilarFileAnalyzer:
    """Main analyzer for similar and problematic files."""

    def __init__(self, min_size_mb: int = 1) -> None:
        self.duplicate_finder = DuplicateFinder(min_size_bytes=min_size_mb * 1024 * 1024)
        self.corrupted_detector = CorruptedFileDetector()
        self.wrong_ext_detector = WrongExtensionDetector()

    def analyze(self, paths: List[str]) -> Dict[str, Any]:
        """Run all similarity analyses."""
        results = {
            'duplicates': [],
            'corrupted': [],
            'wrong_extensions': [],
        }

        # Find duplicates
        duplicates = self.duplicate_finder.find_duplicates(paths)
        results['duplicates'] = duplicates

        # Detect corrupted files
        corrupted = self.corrupted_detector.detect(paths)
        results['corrupted'] = corrupted

        # Detect wrong extensions
        wrong_exts = self.wrong_ext_detector.detect(paths)
        results['wrong_extensions'] = wrong_exts

        # Summary
        results['summary'] = {
            'duplicate_groups': len(duplicates),
            'duplicate_files': sum(g.count for g in duplicates),
            'duplicate_wasted': sum(g.wasted_bytes for g in duplicates),
            'corrupted_files': len(corrupted),
            'wrong_extensions': len(wrong_exts),
        }

        return results
