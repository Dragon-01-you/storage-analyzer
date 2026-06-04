"""Duplicate file detector using 3-stage pipeline.

Stage 1: Group by file size (O(n) — just a dict scan)
Stage 2: For size-collision groups, compute partial hash (first 64KB)
Stage 3: For still-collision groups, compute full SHA-256
         Then verify with byte-level comparison (filecmp.cmp)

This avoids the common pitfall of trusting only hash (even SHA-256)
which could in theory collide.  The final byte-level verify is the
safety net.

Usage:
    dupes = DuplicateDetector(min_size_mb=1).scan(root_paths)
    for group in dupes:
        print(group.wasted_bytes, [str(f.path) for f in group.files])

The detector produces DuplicateGroup objects — never raw file lists.
The user decides which copy to keep (the UI shows size + last_modified).
"""
from __future__ import annotations

import filecmp
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .types import _human_bytes


# Minimum file size to consider for dedup (skip tiny files)
_DEFAULT_MIN_SIZE = 1024 * 1024  # 1MB


@dataclass
class DuplicateFile:
    """A single file in a duplicate group."""
    path: Path
    size: int
    mtime: float  # raw timestamp

    @property
    def human_size(self) -> str:
        return _human_bytes(self.size)


@dataclass
class DuplicateGroup:
    """A group of identical files."""
    files: list[DuplicateFile] = field(default_factory=list)
    hash_sha256: str = ""
    file_size: int = 0

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def wasted_bytes(self) -> int:
        """Space wasted = (count - 1) * size (one copy is kept)."""
        return max(0, (self.count - 1) * self.file_size)

    @property
    def wasted_human(self) -> str:
        return _human_bytes(self.wasted_bytes)


class DuplicateDetector:
    """3-stage duplicate detection pipeline.

    Constructor args:
        min_size_bytes: ignore files smaller than this (default 1MB)
        max_groups: stop after finding this many groups (default 500)
    """

    def __init__(
        self,
        min_size_bytes: int = _DEFAULT_MIN_SIZE,
        max_groups: int = 500,
    ) -> None:
        self.min_size = min_size_bytes
        self.max_groups = max_groups

    def scan(self, roots: list[Path]) -> list[DuplicateGroup]:
        """Run the full pipeline. Returns groups sorted by wasted space."""
        # Stage 1: collect files by size
        size_groups = self._stage1_size_group(roots)
        if not size_groups:
            return []

        # Stage 2: partial hash for size-collision groups
        partial_groups = self._stage2_partial_hash(size_groups)
        if not partial_groups:
            return []

        # Stage 3: full hash + byte verify
        result = self._stage3_full_verify(partial_groups)
        result.sort(key=lambda g: g.wasted_bytes, reverse=True)
        return result[:self.max_groups]

    # ---- Stage 1: group by file size ----------------------------------

    def _stage1_size_group(self, roots: list[Path]) -> dict[int, list[DuplicateFile]]:
        """Group files by size. Files unique in size are not duplicates."""
        by_size: dict[int, list[DuplicateFile]] = {}
        for root in roots:
            if not root.is_dir():
                continue
            try:
                for r, _dirs, files in os.walk(root):
                    for fname in files:
                        fp = Path(r) / fname
                        try:
                            st = fp.stat()
                            if st.st_size >= self.min_size:
                                by_size.setdefault(st.st_size, []).append(
                                    DuplicateFile(path=fp, size=st.st_size, mtime=st.st_mtime)
                                )
                        except OSError:
                            pass
            except OSError:
                pass

        # Keep only groups with >1 file (potential dupes)
        return {size: files for size, files in by_size.items() if len(files) > 1}

    # ---- Stage 2: partial hash (first 64KB) ----------------------------

    def _stage2_partial_hash(
        self, size_groups: dict[int, list[DuplicateFile]]
    ) -> dict[str, list[DuplicateFile]]:
        """Hash first 64KB of each file. Group by (size, partial_hash)."""
        result: dict[str, list[DuplicateFile]] = {}
        block_size = 65536  # 64KB

        for _size, files in size_groups.items():
            for f in files:
                h = self._partial_hash(f.path, block_size)
                if h:
                    key = h
                    result.setdefault(key, []).append(f)

        # Keep only groups with >1 file after partial hash
        return {k: v for k, v in result.items() if len(v) > 1}

    # ---- Stage 3: full SHA-256 + byte-level verify --------------------

    def _stage3_full_verify(
        self, partial_groups: dict[str, list[DuplicateFile]]
    ) -> list[DuplicateGroup]:
        """Full SHA-256 hash, then filecmp.cmp for absolute certainty."""
        result: list[DuplicateGroup] = []

        for _phash, files in partial_groups.items():
            # Group by full SHA-256
            full_groups: dict[str, list[DuplicateFile]] = {}
            for f in files:
                h = self._full_hash(f.path)
                if h:
                    full_groups.setdefault(h, []).append(f)

            for sha, group_files in full_groups.items():
                if len(group_files) < 2:
                    continue

                # Byte-level verify: compare every file against the first
                verified = [group_files[0]]
                for candidate in group_files[1:]:
                    try:
                        if filecmp.cmp(verified[0].path, candidate.path, shallow=False):
                            verified.append(candidate)
                    except OSError:
                        pass

                if len(verified) >= 2:
                    result.append(DuplicateGroup(
                        files=verified,
                        hash_sha256=sha,
                        file_size=verified[0].size,
                    ))

        return result

    # ---- Hash helpers -------------------------------------------------

    @staticmethod
    def _partial_hash(path: Path, block_size: int) -> str | None:
        """SHA-256 of the first block_size bytes."""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                data = f.read(block_size)
                if not data:
                    return None
                h.update(data)
            return h.hexdigest()
        except OSError:
            return None

    @staticmethod
    def _full_hash(path: Path) -> str | None:
        """SHA-256 of the entire file."""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(1048576)  # 1MB chunks
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None
