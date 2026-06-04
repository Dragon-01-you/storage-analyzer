#!/usr/bin/env python3
"""Shared utilities for storage analyzer.

Consolidates common functions used across all scripts to eliminate
code duplication and ensure consistent behavior.

Usage:
    from utils import human, log, get_project_dir, get_scripts_dir
"""
import json
import logging
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ======================================================================
# Project paths
# ======================================================================
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)


def get_scripts_dir():
    return SCRIPTS_DIR


def get_project_dir():
    return PROJECT_DIR


def get_data_path(filename):
    """Get path to a data file in the project root."""
    return os.path.join(PROJECT_DIR, filename)


# ======================================================================
# Logging
# ======================================================================
_logger = None


def get_logger(name="storage-analyzer"):
    """Get or create a configured logger."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(name)
        if not _logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
    return _logger


def log(msg, module=None):
    """Log a message to stderr with optional module prefix."""
    prefix = f"[{module}]" if module else "[sa]"
    print(f"{prefix} {msg}", file=sys.stderr, flush=True)


# ======================================================================
# Size formatting
# ======================================================================
def human(kb):
    """Convert kilobytes to human-readable string."""
    n = float(kb) * 1024
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit not in ("B", "KB") else f"{int(n)} {unit}"
        n /= 1024


def human_bytes(b):
    """Convert bytes to human-readable string."""
    n = float(b)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit not in ("B", "KB") else f"{int(n)} {unit}"
        n /= 1024


def parse_size_to_kb(size_str):
    """Parse human-readable size string to KB. Returns 0 on failure."""
    try:
        parts = size_str.strip().split()
        if len(parts) != 2:
            return 0
        value = float(parts[0])
        unit = parts[1].upper()
        multipliers = {"B": 1/1024, "KB": 1, "MB": 1024, "GB": 1024*1024, "TB": 1024*1024*1024}
        return int(value * multipliers.get(unit, 0))
    except (ValueError, AttributeError):
        return 0


# ======================================================================
# Platform detection
# ======================================================================
def get_platform():
    """Return normalized platform name: 'windows', 'macos', or 'linux'."""
    p = sys.platform
    if p.startswith("win"):
        return "windows"
    elif p == "darwin":
        return "macos"
    else:
        return "linux"


def is_windows():
    return get_platform() == "windows"


def is_macos():
    return get_platform() == "macos"


def is_linux():
    return get_platform() == "linux"


# ======================================================================
# Disk information
# ======================================================================
def get_disk_info():
    """Get disk usage for all mounted drives."""
    disks = []
    
    if is_windows():
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    total, used, free = shutil.disk_usage(drive)
                    disks.append({
                        "name": drive,
                        "total": total,
                        "used": used,
                        "free": free,
                        "total_h": human_bytes(total),
                        "used_h": human_bytes(used),
                        "free_h": human_bytes(free),
                        "percent": round(used / total * 100, 1) if total > 0 else 0,
                    })
                except OSError:
                    continue
    elif is_linux() or is_macos():
        # Use shutil for root partition
        try:
            total, used, free = shutil.disk_usage("/")
            disks.append({
                "name": "/",
                "total": total,
                "used": used,
                "free": free,
                "total_h": human_bytes(total),
                "used_h": human_bytes(used),
                "free_h": human_bytes(free),
                "percent": round(used / total * 100, 1) if total > 0 else 0,
            })
        except OSError:
            pass
        
        # Try to detect mounted partitions on Linux
        if is_linux():
            try:
                with open("/proc/mounts", "r") as f:
                    mounts = f.readlines()
                seen = {"/"}
                for line in mounts:
                    parts = line.split()
                    if len(parts) >= 2:
                        mount_point = parts[1]
                        # Skip virtual/snap/docker filesystems
                        if any(mount_point.startswith(p) for p in (
                            "/proc", "/sys", "/dev", "/run", "/snap", "/boot/efi",
                            "/var/lib/docker", "/tmp"
                        )):
                            continue
                        if mount_point in seen:
                            continue
                        seen.add(mount_point)
                        try:
                            total, used, free = shutil.disk_usage(mount_point)
                            if total > 1024**3:  # Only show partitions > 1GB
                                disks.append({
                                    "name": mount_point,
                                    "total": total,
                                    "used": used,
                                    "free": free,
                                    "total_h": human_bytes(total),
                                    "used_h": human_bytes(used),
                                    "free_h": human_bytes(free),
                                    "percent": round(used / total * 100, 1) if total > 0 else 0,
                                })
                        except OSError:
                            continue
            except OSError:
                pass
    
    return disks


def get_system_info():
    """Get system information."""
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python": platform.python_version(),
    }
    
    disks = get_disk_info()
    if disks:
        # Primary disk (first one, usually C: or /)
        primary = disks[0]
        info["disk_total"] = primary["total_h"]
        info["disk_used"] = primary["used_h"]
        info["disk_free"] = primary["free_h"]
        info["disk_percent"] = primary["percent"]
    info["disks"] = disks
    
    return info


# ======================================================================
# File type classification
# ======================================================================
FILE_TYPE_CATEGORIES = {
    "video": {
        "extensions": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"},
        "label": "视频文件",
        "tier_hint": "yellow",
    },
    "image": {
        "extensions": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".heic", ".heif", ".raw", ".cr2", ".nef"},
        "label": "图片文件",
        "tier_hint": "yellow",
    },
    "archive": {
        "extensions": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".img", ".dmg", ".cab"},
        "label": "压缩包/镜像",
        "tier_hint": "yellow",
    },
    "document": {
        "extensions": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".rtf", ".csv", ".odt"},
        "label": "文档文件",
        "tier_hint": "yellow",
    },
    "executable": {
        "extensions": {".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".deb", ".rpm", ".pkg", ".app"},
        "label": "可执行文件/安装包",
        "tier_hint": "green",
    },
    "code": {
        "extensions": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".lua", ".r"},
        "label": "代码文件",
        "tier_hint": "yellow",
    },
    "data": {
        "extensions": {".json", ".xml", ".yaml", ".yml", ".toml", ".sql", ".db", ".sqlite", ".sqlite3", ".mdb"},
        "label": "数据文件",
        "tier_hint": "yellow",
    },
    "virtual_machine": {
        "extensions": {".vmdk", ".vdi", ".vhd", ".vhdx", ".qcow2", ".vbox", ".vmx", ".vmwarevm"},
        "label": "虚拟机磁盘",
        "tier_hint": "yellow",
    },
    "font": {
        "extensions": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
        "label": "字体文件",
        "tier_hint": "green",
    },
    "log": {
        "extensions": {".log", ".log.old", ".log.1", ".log.2", ".log.3"},
        "label": "日志文件",
        "tier_hint": "green",
    },
    "temp": {
        "extensions": {".tmp", ".temp", ".bak", ".swp", ".cache"},
        "label": "临时文件",
        "tier_hint": "green",
    },
}


def classify_file_type(filepath):
    """Classify a file by its extension. Returns (category, label, tier_hint)."""
    ext = os.path.splitext(filepath)[1].lower()
    for category, info in FILE_TYPE_CATEGORIES.items():
        if ext in info["extensions"]:
            return category, info["label"], info["tier_hint"]
    return "other", "其他文件", "yellow"


# ======================================================================
# Large file scanner
# ======================================================================
def scan_large_files(paths, min_size_bytes=100*1024*1024, max_files=500, timeout=60):
    """Scan for individual large files across paths.
    
    Args:
        paths: List of directory paths to scan
        min_size_bytes: Minimum file size in bytes (default 100MB)
        max_files: Maximum number of files to return
        timeout: Scan timeout in seconds
    
    Returns:
        List of dicts with file info, sorted by size desc
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    large_files = []
    deadline = time.time() + timeout
    
    def _scan_path(root_path):
        files = []
        try:
            for entry in os.scandir(root_path):
                if time.time() > deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        if size >= min_size_bytes:
                            category, label, tier = classify_file_type(entry.path)
                            files.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size_bytes": size,
                                "size_kb": size // 1024,
                                "size_h": human_bytes(size),
                                "category": category,
                                "category_label": label,
                                "tier_hint": tier,
                                "mtime": entry.stat(follow_symlinks=False).st_mtime,
                            })
                    elif entry.is_dir(follow_symlinks=False):
                        # Skip known uninteresting dirs
                        skip_dirs = {".git", "node_modules", "__pycache__", ".svn"}
                        if entry.name in skip_dirs:
                            continue
                        files.extend(_scan_path(entry.path))
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        return files
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_scan_path, p): p for p in paths if os.path.exists(p)}
        for future in as_completed(futures):
            try:
                large_files.extend(future.result())
            except Exception:
                continue
    
    # Sort by size, limit results
    large_files.sort(key=lambda x: x["size_bytes"], reverse=True)
    return large_files[:max_files]


# ======================================================================
# Old file detection
# ======================================================================
def find_old_files(paths, days=180, min_size_bytes=50*1024*1024, max_files=200, timeout=60):
    """Find files not accessed in the specified number of days.
    
    Args:
        paths: List of directory paths to scan
        days: Number of days since last access
        min_size_bytes: Minimum file size
        max_files: Maximum results
        timeout: Scan timeout in seconds
    
    Returns:
        List of dicts with old file info
    """
    import time
    
    cutoff = time.time() - (days * 86400)
    old_files = []
    deadline = time.time() + timeout
    
    def _scan(root_path):
        results = []
        try:
            for entry in os.scandir(root_path):
                if time.time() > deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        stat = entry.stat(follow_symlinks=False)
                        # Use the older of atime and mtime
                        last_used = min(stat.st_atime, stat.st_mtime)
                        if last_used < cutoff and stat.st_size >= min_size_bytes:
                            age_days = int((time.time() - last_used) / 86400)
                            category, label, tier = classify_file_type(entry.path)
                            results.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size_bytes": stat.st_size,
                                "size_kb": stat.st_size // 1024,
                                "size_h": human_bytes(stat.st_size),
                                "age_days": age_days,
                                "last_used": datetime.fromtimestamp(last_used).strftime("%Y-%m-%d"),
                                "category": category,
                                "category_label": label,
                            })
                    elif entry.is_dir(follow_symlinks=False):
                        skip_dirs = {".git", "node_modules", "__pycache__", ".svn", "Windows", "System32"}
                        if entry.name in skip_dirs:
                            continue
                        results.extend(_scan(entry.path))
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        return results
    
    all_results = []
    for p in paths:
        if os.path.exists(p):
            all_results.extend(_scan(p))
    
    all_results.sort(key=lambda x: x["size_bytes"], reverse=True)
    return all_results[:max_files]


# ======================================================================
# JSON helpers
# ======================================================================
def load_json(filepath, default=None):
    """Load JSON file with error handling."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default if default is not None else {}


def save_json(filepath, data, indent=2):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# ======================================================================
# Scan cache (incremental scanning)
# ======================================================================
CACHE_FILE = os.path.join(PROJECT_DIR, ".scan_cache.json")


def load_scan_cache():
    """Load scan cache for incremental scanning."""
    return load_json(CACHE_FILE, {"entries": {}, "last_scan": None})


def save_scan_cache(cache):
    """Save scan cache."""
    save_json(CACHE_FILE, cache)


def get_cached_size(path, cache):
    """Get cached directory size if the directory hasn't changed.
    
    Uses mtime of the directory entry to detect changes.
    Returns (size_kb, is_cache_hit).
    """
    try:
        mtime = os.path.getmtime(path)
        cached = cache.get("entries", {}).get(path)
        if cached and cached.get("mtime") == mtime:
            return cached.get("size_kb", 0), True
    except OSError:
        pass
    return 0, False


def update_cache_entry(path, size_kb, cache):
    """Update a cache entry."""
    try:
        mtime = os.path.getmtime(path)
        cache.setdefault("entries", {})[path] = {
            "size_kb": size_kb,
            "mtime": mtime,
            "updated": datetime.now().isoformat(),
        }
    except OSError:
        pass


def cleanup_cache(cache, max_age_days=30):
    """Remove stale cache entries."""
    cutoff = datetime.now().timestamp() - (max_age_days * 86400)
    entries = cache.get("entries", {})
    stale = []
    for path, entry in entries.items():
        try:
            updated = datetime.fromisoformat(entry.get("updated", "2000-01-01"))
            if updated.timestamp() < cutoff:
                stale.append(path)
        except (ValueError, TypeError):
            stale.append(path)
    for key in stale:
        del entries[key]
