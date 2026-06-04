"""Engine Core: FunnelScanner + PluginRegistry.

FunnelScanner is the ONLY thing that touches the disk heavily.
Its job: produce DirectorySummary objects (compressed), never raw trees.

The funnel is two-stage:
  1. Top: cheap, fast, rule-based (finds Temp/Cache in <5s)
  2. Bottom: expensive, slow, heuristic (large dirs, deduped by mtime)
"""
from __future__ import annotations
import os
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from .types import DirectorySummary, ScanConfig


# ===========================================================================
# FunnelScanner
# ===========================================================================

class FunnelScanner:
    """Two-stage scanner. Stage 1 cheap, stage 2 deep.

    Contract: NEVER returns a DirectorySummary with full file list.
    Each summary has at most 20 feature_files and 10 feature_dirs.
    """

    # Hard-coded fast paths (Level 1 fingerprints for stage 1)
    FAST_TARGETS: list[tuple[str, str]] = [
        (r"%TEMP%", "temp"),
        (r"%LOCALAPPDATA%\Microsoft\Windows\Explorer", "thumb"),
        (r"%LOCALAPPDATA%\CrashDumps", "crash"),
        (r"%LOCALAPPDATA%\npm-cache", "npm"),
        (r"%LOCALAPPDATA%\pip\cache", "pip"),
        (r"%USERPROFILE%\.cargo\registry", "cargo"),
        (r"%LOCALAPPDATA%\JetBrains", "jb"),
    ]

    def __init__(self, config: ScanConfig) -> None:
        self.config = config

    def scan(self) -> list[DirectorySummary]:
        summaries: list[DirectorySummary] = []
        # Stage 1: fast, known locations
        for template, key in self.FAST_TARGETS:
            path = self._expand(template)
            if path and path.is_dir():
                summaries.append(self._summarize(path, max_depth=2, time_budget_s=5))
        # Stage 2: deep, everything in target_paths
        for target in self.config.target_paths:
            if not target.is_dir():
                continue
            for sub in self._walk_top(target, max_depth=2, time_budget_s=30):
                if self._should_deep_dive(sub):
                    summaries.append(self._summarize(sub, max_depth=4, time_budget_s=20))
        return summaries

    # ---- helpers -------------------------------------------------------

    @staticmethod
    def _expand(template: str) -> Path | None:
        expanded = os.path.expandvars(os.path.expanduser(template))
        p = Path(expanded)
        return p if p.exists() else None

    def _walk_top(self, root: Path, max_depth: int, time_budget_s: int) -> Iterator[Path]:
        """Yield subdirectories at depth 1..max_depth under root, with time budget."""
        deadline = time.time() + time_budget_s
        for r, dirs, _ in os.walk(root):
            depth = Path(r).relative_to(root).parts
            if len(depth) >= max_depth:
                dirs.clear()
                continue
            if time.time() > deadline:
                break
            # Skip excluded paths
            if any(self._is_excluded(Path(r) / d) for d in dirs):
                dirs[:] = [d for d in dirs if not self._is_excluded(Path(r) / d)]
            yield Path(r)

    def _is_excluded(self, p: Path) -> bool:
        s = str(p).lower()
        for ex in self.config.exclude_paths:
            if ex.match(s):
                return True
        return False

    def _should_deep_dive(self, p: Path) -> bool:
        """Cheap size estimate. Skip tiny or system dirs."""
        try:
            # Quick sampling: count entries, sum 10 files
            entries = list(os.scandir(p))
            if not entries:
                return False
            sample = 0
            for e in entries[:20]:
                try:
                    sample += e.stat().st_size
                except OSError:
                    pass
            estimated = sample * (len(entries) / min(len(entries), 20))
            return estimated >= self.config.min_size_mb * 1024**2
        except (PermissionError, OSError):
            return False

    def _summarize(self, p: Path, max_depth: int, time_budget_s: int) -> DirectorySummary:
        """Walk the directory, but stop at max_depth, never store the full tree."""
        total = 0
        count = 0
        last_access = None
        last_modified = None
        feature_files: list[str] = []
        feature_dirs: list[str] = []
        deadline = time.time() + time_budget_s

        try:
            for r, dirs, files in os.walk(p):
                if time.time() > deadline:
                    break
                depth = Path(r).relative_to(p).parts
                if len(depth) >= max_depth:
                    dirs.clear()
                for f in files:
                    full = Path(r) / f
                    try:
                        st = full.stat()
                        total += st.st_size
                        count += 1
                        la = st.st_atime
                        lm = st.st_mtime
                        if last_access is None or la > last_access:
                            last_access = la
                        if last_modified is None or lm > last_modified:
                            last_modified = lm
                        # Capture "feature files" — only ones that match known
                        # fingerprints (package.json, .vmdk, .vmx, etc.)
                        if _is_feature_file(f) and len(feature_files) < 20:
                            feature_files.append(f)
                    except OSError:
                        pass
                for d in dirs:
                    if _is_feature_dir(d) and len(feature_dirs) < 10:
                        feature_dirs.append(d)
        except OSError:
            pass

        from datetime import datetime
        return DirectorySummary(
            path=p,
            total_bytes=total,
            file_count=count,
            last_access=datetime.fromtimestamp(last_access) if last_access else None,
            last_modified=datetime.fromtimestamp(last_modified) if last_modified else None,
            feature_files=feature_files,
            feature_dirs=feature_dirs,
            has_lock_files=any(p.glob("*.lck")),
            contains_user_data=_dir_contains_user_data(p),
        )


# Heuristics for "feature file" — files that survive compression
_FEATURE_FILE_PATTERNS = (
    "package.json", "package-lock.json", "yarn.lock", "Cargo.toml",
    "go.mod", "requirements.txt", "Pipfile", "pyproject.toml",
    "README", "README.md", "LICENSE",
    "*.vmdk", "*.vmx", "*.vmsn", "*.vmem",
    "ext4.vhdx",
    "*.iso", "setup.exe", "*.dmg",
)


def _is_feature_file(name: str) -> bool:
    """Return True if this filename is worth keeping in the summary.

    The summary never has a full file list — only files that hint at
    what the directory IS. A 1MB installer is more useful than 200
    random .dll files in the AI's view.
    """
    import fnmatch
    name_lower = name.lower()
    for pat in _FEATURE_FILE_PATTERNS:
        if fnmatch.fnmatch(name_lower, pat.lower()):
            return True
    return False


_FEATURE_DIR_NAMES = {
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    "target", "build", "dist", ".gradle", ".idea", ".vscode",
    "Logs", "Cache", "GPUCache", "shader_cache",
}


def _is_feature_dir(name: str) -> bool:
    return name in _FEATURE_DIR_NAMES


_USER_DATA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",  # photos
    ".mp4", ".mov", ".avi", ".mkv",                      # videos
    ".docx", ".doc", ".pdf", ".xlsx", ".pptx",          # office
    ".psd", ".ai", ".sketch", ".fig",                    # design
}


def _dir_contains_user_data(p: Path) -> bool:
    """Cheap: sample a few files, see if any look like user content."""
    try:
        for e in os.scandir(p):
            if e.is_file():
                ext = os.path.splitext(e.name)[1].lower()
                if ext in _USER_DATA_EXTENSIONS:
                    return True
                if len(e.name) > 3:
                    return False
    except OSError:
        pass
    return False


# ===========================================================================
# PluginRegistry
# ===========================================================================

class _CleanerProtocol(Protocol):
    """Minimum interface a v8 cleaner must satisfy."""
    name: str
    def analyze(self, summary: DirectorySummary) -> bool:
        """Return True if this cleaner wants to act on this summary."""
    def execute(self, summary: DirectorySummary) -> tuple[int, str]:
        """Perform the actual cleanup. Returns (bytes_freed, status_msg)."""


class PluginRegistry:
    """In-process plugin registry. Hot-pluggable.

    Plugins are pure-Python classes implementing _CleanerProtocol.
    Discovery is by either:
      - explicit register() call
      - importlib.metadata entry_points (planned for v8.1)
    """

    def __init__(self) -> None:
        self._plugins: list[_CleanerProtocol] = []

    def register(self, plugin: _CleanerProtocol) -> None:
        if plugin.name in {p.name for p in self._plugins}:
            raise ValueError(f"Plugin {plugin.name!r} already registered")
        self._plugins.append(plugin)

    def unregister(self, name: str) -> None:
        self._plugins = [p for p in self._plugins if p.name != name]

    def all(self) -> list[_CleanerProtocol]:
        return list(self._plugins)

    def run(self, summary: DirectorySummary) -> list[tuple[str, int, str]]:
        """Run every applicable plugin on a summary. Returns per-plugin results."""
        results = []
        for p in self._plugins:
            try:
                if p.analyze(summary):
                    freed, msg = p.execute(summary)
                    results.append((p.name, freed, msg))
            except Exception as e:
                results.append((p.name, 0, f"error: {e!r}"))
        return results
