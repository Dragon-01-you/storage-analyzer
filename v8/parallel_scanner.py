"""Parallel scanner for improved performance.

Uses ThreadPoolExecutor to scan multiple directories concurrently.
Reduces scan time on multi-core systems with multiple drives.
"""
from __future__ import annotations
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Callable

from .types import DirectorySummary, ScanConfig


@dataclass
class ScanTask:
    """A single scan task."""
    path: Path
    depth: int = 0
    max_depth: int = 4
    timeout: int = 30


@dataclass
class ScanResult:
    """Result of a single scan task."""
    path: Path
    total_bytes: int = 0
    file_count: int = 0
    dir_count: int = 0
    error: str = ""
    elapsed_s: float = 0


class ParallelScanner:
    """Scan multiple directories in parallel.

    Benefits:
    - Multi-drive systems: scan C:, D:, E: concurrently
    - Large directories: split into sub-tasks
    - I/O bound: threads help even on single core

    Usage:
        scanner = ParallelScanner(max_workers=4)
        results = scanner.scan([Path("C:\\"), Path("D:\\")])
    """

    def __init__(self, max_workers: int = 4, timeout: int = 30) -> None:
        self.max_workers = max_workers
        self.timeout = timeout

    def scan(self, paths: List[Path], max_depth: int = 4) -> List[ScanResult]:
        """Scan multiple paths in parallel."""
        if not paths:
            return []

        # Single path - no need for parallel
        if len(paths) == 1:
            return [self._scan_single(ScanTask(
                path=paths[0], max_depth=max_depth, timeout=self.timeout
            ))]

        # Multiple paths - parallel scan
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = [
                ScanTask(path=p, max_depth=max_depth, timeout=self.timeout)
                for p in paths
            ]
            futures = {
                executor.submit(self._scan_single, task): task
                for task in tasks
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = futures[future]
                    results.append(ScanResult(
                        path=task.path,
                        error=str(e)
                    ))
        return results

    def _scan_single(self, task: ScanTask) -> ScanResult:
        """Scan a single directory tree."""
        start = time.time()
        result = ScanResult(path=task.path)
        deadline = start + task.timeout

        try:
            real = str(task.path.resolve())
            for root, dirs, files in os.walk(task.path):
                if time.time() > deadline:
                    break

                # Depth check
                depth = root[len(real):].count(os.sep)
                if depth >= task.max_depth:
                    dirs.clear()

                result.dir_count += 1

                for f in files:
                    try:
                        fp = os.path.join(root, f)
                        st = os.stat(fp)
                        result.total_bytes += st.st_size
                        result.file_count += 1
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError) as e:
            result.error = str(e)

        result.elapsed_s = time.time() - start
        return result

    def scan_with_callback(
        self,
        paths: List[Path],
        callback: Callable[[ScanResult], None],
        max_depth: int = 4
    ) -> List[ScanResult]:
        """Scan with progress callback for each completed path."""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = [
                ScanTask(path=p, max_depth=max_depth, timeout=self.timeout)
                for p in paths
            ]
            futures = {
                executor.submit(self._scan_single, task): task
                for task in tasks
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    callback(result)
                except Exception as e:
                    task = futures[future]
                    result = ScanResult(path=task.path, error=str(e))
                    results.append(result)
                    callback(result)
        return results


def scan_parallel(
    paths: List[Path],
    max_workers: int = 4,
    max_depth: int = 4,
    timeout: int = 30
) -> List[ScanResult]:
    """Convenience function for parallel scanning."""
    scanner = ParallelScanner(max_workers=max_workers, timeout=timeout)
    return scanner.scan(paths, max_depth=max_depth)
