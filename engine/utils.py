"""Utility functions for storage analyzer."""
import json
import os
import shutil
import sys
import time
from datetime import datetime

# Platform detection
HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = not IS_WIN and not IS_MAC
SYSROOT = os.environ.get("SystemRoot", "C:\\Windows") if IS_WIN else "/"

# Config loading
def _load_cfg():
    """Load config.json with error handling."""
    try:
        config_path = os.path.join(os.path.dirname(HERE), "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"scan": {}, "protected_paths": [], "classify": {"green": [], "red": [], "known_apps": {}}}

CFG = _load_cfg()

# Platform paths
def plat_paths():
    """Get platform-specific paths."""
    p = {
        "home": HOME,
        "downloads": os.path.join(HOME, "Downloads"),
        "desktop": os.path.join(HOME, "Desktop")
    }
    if IS_WIN:
        p.update({
            "temp": os.environ.get("TEMP", os.path.join(HOME, "AppData\\Local\\Temp")),
            "local": os.path.join(HOME, "AppData\\Local"),
            "roaming": os.path.join(HOME, "AppData\\Roaming"),
            "progfiles": os.environ.get("ProgramFiles", "C:\\Program Files"),
            "progfiles86": os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            "crash_dumps": os.path.join(HOME, "AppData\\Local\\CrashDumps"),
            "memory_dmp": os.path.join(SYSROOT, "MEMORY.DMP"),
            "minidump": os.path.join(SYSROOT, "Minidump"),
            "cbs_logs": os.path.join(SYSROOT, "Logs\\CBS"),
            "wu_cache": os.path.join(SYSROOT, "SoftwareDistribution\\Download"),
            "prefetch": os.path.join(SYSROOT, "Prefetch"),
            "docker": os.path.join(HOME, "AppData\\Local\\Docker"),
            "gpu_cache": os.path.join(HOME, "AppData\\Local\\NVIDIA"),
            "browsers": {
                "Chrome": os.path.join(HOME, "AppData\\Local\\Google\\Chrome\\User Data\\Default"),
                "Edge": os.path.join(HOME, "AppData\\Local\\Microsoft\\Edge\\User Data\\Default"),
                "Firefox": os.path.join(HOME, "AppData\\Local\\Mozilla\\Firefox\\Profiles"),
            },
            "chat": {
                "WeChat": os.path.join(HOME, "Documents\\xwechat_files"),
                "Tencent": os.path.join(HOME, "AppData\\Roaming\\Tencent"),
            },
        })
    elif IS_LINUX:
        p.update({
            "temp": "/tmp",
            "var_log": "/var/log",
            "var_cache": "/var/cache",
            "opt": "/opt"
        })
    return p


PP = plat_paths()

# Protected paths
PROTECTED = set()
for pp in CFG.get("protected_paths", []):
    try:
        PROTECTED.add(os.path.realpath(os.path.expanduser(pp)))
    except OSError:
        pass

# Cache paths
CACHE_DIR = os.path.join(HOME, ".cache", "storage-analyzer") if not IS_WIN else os.path.join(os.environ.get("LOCALAPPDATA", HOME), "storage-analyzer")
SCAN_CACHE_FILE = os.path.join(CACHE_DIR, "scan_cache.json")
HISTORY_FILE = os.path.join(CACHE_DIR, "history.json")
AUDIT_LOG = os.path.join(CACHE_DIR, "deletions.log")


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError:
        pass


def hb(b):
    """Convert bytes to human-readable string."""
    if b == 0:
        return "0B"
    n = float(b)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f}{u}" if n < 100 else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


def hk(kb):
    """Convert kilobytes to human-readable string."""
    return hb(kb * 1024)


def log(msg, lvl=1):
    """Log message to stderr."""
    if lvl <= int(os.environ.get("SA_VERBOSE", "1")):
        print(f"[sa] {msg}", file=sys.stderr, flush=True)


def szf(path):
    """Get file size safely."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def szd(path, max_depth=4, timeout=20):
    """Get directory size with depth limit and timeout."""
    total = 0
    deadline = time.time() + timeout
    try:
        real = os.path.realpath(path)
        for root, dirs, files in os.walk(path):
            if time.time() > deadline:
                break
            depth = root[len(real):].count(os.sep)
            if depth >= max_depth:
                dirs.clear()
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _fast_szd(path, timeout=10):
    """Fast directory size using os.scandir (faster than os.walk for large dirs)."""
    total = 0
    deadline = time.time() + timeout
    stack = [path]
    while stack and time.time() < deadline:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue
    return total


def disks():
    """Get disk usage for all drives."""
    d = {}
    if IS_WIN:
        for letter in "CDEFGH":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    total, used, free = shutil.disk_usage(drive)
                    if total > 0:
                        d[letter] = {
                            "t": total,
                            "u": used,
                            "f": free,
                            "th": hb(total),
                            "uh": hb(used),
                            "fh": hb(free),
                            "p": round(used / total * 100, 1)
                        }
                except OSError:
                    continue
    return d



def load_scan_cache():
    """Load scan cache."""
    try:
        with open(SCAN_CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_scan_cache(cache):
    """Save scan cache."""
    _ensure_cache_dir()
    try:
        with open(SCAN_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except OSError:
        pass


def load_history():
    """Load history data."""
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_history(dd, hist):
    """Save history data."""
    _ensure_cache_dir()
    ts = time.time()
    for n, d in dd.items():
        hist.setdefault(n, []).append([ts, d["p"]])
        if len(hist[n]) > 60:
            hist[n] = hist[n][-60:]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(hist, f)
    except OSError:
        pass


def audit_log(action, path, result, size=0):
    """Append deletion record to audit log."""
    _ensure_cache_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {action} | {path} | {result} | {size} bytes\n"
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
