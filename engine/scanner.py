"""Scanner module - handles all scanning operations."""
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .utils import (
    HOME, IS_WIN, SYSROOT, PP, CFG, log, hk, szd, szf, _fast_szd,
    load_scan_cache, save_scan_cache
)


def scan_dir(path, min_kb=51200, use_cache=False, cache=None):
    """Scan a single directory and return items above threshold."""
    if not os.path.isdir(path):
        return []
    results = []
    try:
        entries = list(os.scandir(path))
    except (PermissionError, OSError):
        return [{"n": "(denied)", "p": path, "k": 0, "h": "?"}]
    
    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if use_cache and cache is not None:
                    size, _ = _cached_szd(entry.path, cache, 3, 15)
                else:
                    size = szd(entry.path, 3, 15)
            else:
                size = entry.stat().st_size
            kb = size // 1024
            if kb < min_kb:
                continue
            results.append({
                "n": entry.name,
                "p": entry.path,
                "k": kb,
                "h": hk(kb)
            })
        except (PermissionError, OSError):
            continue
    
    results.sort(key=lambda x: x["k"], reverse=True)
    return results


def _cached_szd(path, cache, max_depth=4, timeout=20):
    """Get directory size with cache support."""
    try:
        real = os.path.realpath(path)
        mtime = os.path.getmtime(real)
        entry = cache.get(real)
        if entry and entry.get("mtime") == mtime:
            return entry["size"], True  # cache hit
    except OSError:
        pass
    
    size = szd(path, max_depth, timeout)
    try:
        real = os.path.realpath(path)
        cache[real] = {
            "size": size,
            "mtime": os.path.getmtime(real),
            "ts": time.time()
        }
    except OSError:
        pass
    return size, False


def scan_all(use_cache=True):
    """Scan all user directories in parallel."""
    g = {}
    cache = load_scan_cache() if use_cache else {}
    targets = [
        ("temp", PP.get("temp"), 51200),
        ("downloads", PP.get("downloads"), 51200),
        ("desktop", PP.get("desktop"), 51200),
        ("local", PP.get("local"), 51200),
        ("roaming", PP.get("roaming"), 51200)
    ]
    
    # Parallel scanning using configured workers
    workers = CFG.get("scan", {}).get("workers", 4)
    valid = [(n, p, m) for n, p, m in targets if p and os.path.exists(p)]
    
    if len(valid) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(valid))) as ex:
            futs = {ex.submit(scan_dir, p, m, use_cache, cache): n for n, p, m in valid}
            for fut in as_completed(futs):
                n = futs[fut]
                try:
                    g[n] = fut.result()
                except Exception:
                    g[n] = []
    else:
        for n, p, m in valid:
            g[n] = scan_dir(p, m, use_cache, cache)
    
    if use_cache:
        save_scan_cache(cache)
    return g


def scan_sys():
    """Scan system files and return cleanup candidates."""
    items = []
    
    # MEMORY.DMP
    mp = PP.get("memory_dmp", "")
    if mp and os.path.isfile(mp):
        s = szf(mp)
        k = s // 1024
        items.append({
            "n": "MEMORY.DMP", "p": mp, "k": k, "h": hk(k),
            "safe": True, "reason": "System memory dump",
            "risk": "none", "prio": 1, "cat": "system"
        })
    
    # CBS Logs
    cbs = PP.get("cbs_logs", "")
    if cbs and os.path.isdir(cbs):
        s = szd(cbs, 2, 10)
        k = s // 1024
        if k > 1024:
            items.append({
                "n": "CBS Logs", "p": cbs, "k": k, "h": hk(k),
                "safe": True, "reason": "Windows update logs",
                "risk": "none", "prio": 1, "cat": "system"
            })
    
    # Windows Update Cache
    wu = PP.get("wu_cache", "")
    if wu and os.path.isdir(wu):
        s = szd(wu, 2, 10)
        k = s // 1024
        if k > 1024:
            items.append({
                "n": "Windows Update Cache", "p": wu, "k": k, "h": hk(k),
                "safe": True, "reason": "Update downloads",
                "risk": "none", "prio": 1, "cat": "system"
            })
    
    # Prefetch
    pf = PP.get("prefetch", "")
    if pf and os.path.isdir(pf):
        s = szd(pf, 1, 5)
        k = s // 1024
        if k > 1024:
            items.append({
                "n": "Prefetch", "p": pf, "k": k, "h": hk(k),
                "safe": True, "reason": "Prefetch cache",
                "risk": "none", "prio": 1, "cat": "system"
            })
    
    # CrashDumps
    cd = PP.get("crash_dumps", "")
    if cd and os.path.isdir(cd):
        s = szd(cd, 2, 10)
        k = s // 1024
        if k > 1024:
            items.append({
                "n": "CrashDumps", "p": cd, "k": k, "h": hk(k),
                "safe": True, "reason": "Crash dumps",
                "risk": "none", "prio": 1, "cat": "system"
            })
    
    # GPU cache
    gc = PP.get("gpu_cache", "")
    if gc and os.path.isdir(gc):
        s = szd(gc, 3, 10)
        k = s // 1024
        if k > 1024:
            items.append({
                "n": "NVIDIA Cache", "p": gc, "k": k, "h": hk(k),
                "safe": True, "reason": "GPU shader cache",
                "risk": "none", "prio": 1, "cat": "system"
            })
    
    # Docker
    dk = PP.get("docker", "")
    if dk and os.path.isdir(dk):
        s = szd(dk, 3, 10)
        k = s // 1024
        if k > 10240:
            items.append({
                "n": "Docker Data", "p": dk, "k": k, "h": hk(k),
                "safe": False, "reason": "Docker images/containers - review before deleting",
                "risk": "med", "prio": 2, "cat": "dev"
            })
    
    # Browsers
    br = PP.get("browsers", {})
    for bname, bpath in br.items():
        if bpath and os.path.isdir(bpath):
            cache_p = os.path.join(bpath, "Cache" if bname != "Firefox" else "")
            if os.path.isdir(cache_p):
                s = szd(cache_p, 3, 10)
                k = s // 1024
                if k > 51200:
                    items.append({
                        "n": f"{bname} Cache", "p": cache_p, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{bname} browser cache",
                        "risk": "none", "prio": 1, "cat": "browser"
                    })
            # Entire profile
            s = szd(bpath, 3, 10)
            k = s // 1024
            if k > 102400:
                items.append({
                    "n": f"{bname} Profile", "p": bpath, "k": k, "h": hk(k),
                    "safe": False, "reason": f"{bname} browser profile - review before deleting",
                    "risk": "med", "prio": 3, "cat": "browser"
                })
    
    # Chat apps
    ch = PP.get("chat", {})
    for cname, cpath in ch.items():
        if cpath and os.path.isdir(cpath):
            s = szd(cpath, 3, 15)
            k = s // 1024
            if k > 102400:
                items.append({
                    "n": cname, "p": cpath, "k": k, "h": hk(k),
                    "safe": False, "reason": f"{cname} chat data - review before deleting",
                    "risk": "med", "prio": 3, "cat": "chat"
                })
    
    # VMware / VM dirs
    if IS_WIN:
        for drv in ("D:\\", "E:\\"):
            if not os.path.exists(drv):
                continue
            for cand in ("Virtual Machines", "VMs", "vm", "VMware", "kali", "ubuntu"):
                vp = os.path.join(drv, cand)
                if os.path.isdir(vp):
                    s = szd(vp, 3, 20)
                    k = s // 1024
                    if k > 102400:
                        items.append({
                            "n": cand, "p": vp, "k": k, "h": hk(k),
                            "safe": False, "reason": f"VM directory on {drv[0]} - review snapshots",
                            "risk": "medium", "prio": 3, "cat": "vm"
                        })
    
    # === Industry-standard cleanup targets ===
    if IS_WIN:
        # Recycle Bin
        try:
            import ctypes
            from ctypes import wintypes
            class SHQUERYRBINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]
            info = SHQUERYRBINFO()
            info.cbSize = ctypes.sizeof(info)
            hr = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
            if hr == 0 and info.i64Size > 0:
                rb_kb = info.i64Size // 1024
                items.append({
                    "n": "Recycle Bin", "p": "Recycle Bin", "k": rb_kb, "h": hk(rb_kb),
                    "safe": True, "reason": "Recycle Bin contents",
                    "risk": "none", "prio": 1, "cat": "system", "dism": False
                })
        except Exception:
            pass
        
        # Thumbnail Cache
        thumb_dir = os.path.join(HOME, "AppData\\Local\\Microsoft\\Windows\\Explorer")
        if os.path.isdir(thumb_dir):
            thumb_sz = 0
            try:
                for f in os.listdir(thumb_dir):
                    if f.lower().startswith("thumbcache") or f.lower().startswith("iconcache"):
                        thumb_sz += szf(os.path.join(thumb_dir, f))
            except OSError:
                pass
            if thumb_sz > 1048576:
                items.append({
                    "n": "Thumbnail Cache", "p": thumb_dir, "k": thumb_sz // 1024, "h": hk(thumb_sz // 1024),
                    "safe": True, "reason": "Explorer thumbnail/icon cache",
                    "risk": "none", "prio": 1, "cat": "system"
                })
        
        # Delivery Optimization
        do_path = os.path.join(SYSROOT, "SoftwareDistribution\\DeliveryOptimization")
        if os.path.isdir(do_path):
            s = szd(do_path, 2, 10)
            k = s // 1024
            if k > 1024:
                items.append({
                    "n": "Delivery Optimization", "p": do_path, "k": k, "h": hk(k),
                    "safe": True, "reason": "Windows Update delivery cache",
                    "risk": "none", "prio": 1, "cat": "system"
                })
        
        # WER (Windows Error Reports)
        wer_path = os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft\\Windows\\WER")
        if os.path.isdir(wer_path):
            s = szd(wer_path, 3, 10)
            k = s // 1024
            if k > 1024:
                items.append({
                    "n": "Error Reports", "p": wer_path, "k": k, "h": hk(k),
                    "safe": True, "reason": "Windows Error Reporting data",
                    "risk": "none", "prio": 1, "cat": "system"
                })
        
        # WinSxS (use DISM, not manual delete)
        sxs_path = os.path.join(SYSROOT, "WinSxS")
        if os.path.isdir(sxs_path):
            s = szd(sxs_path, 2, 15)
            k = s // 1024
            if k > 1048576:
                items.append({
                    "n": "WinSxS Component Store", "p": sxs_path, "k": k, "h": hk(k),
                    "safe": True, "reason": "Windows component store - use DISM",
                    "risk": "none", "prio": 1, "cat": "system", "dism": True
                })
        
        # Dev toolchain caches
        dev_caches = [
            ("npm Cache", os.path.join(HOME, "AppData\\Local\\npm-cache"), 102400),
            ("pip Cache", os.path.join(HOME, "AppData\\Local\\pip\\cache"), 102400),
            ("Cargo Cache", os.path.join(HOME, ".cargo\\registry\\cache"), 102400),
            ("Yarn Cache", os.path.join(HOME, "AppData\\Local\\Yarn\\Cache"), 102400),
            ("pnpm Store", os.path.join(HOME, "AppData\\Local\\pnpm\\store"), 102400),
        ]
        for name, path, threshold in dev_caches:
            if os.path.isdir(path):
                s = _fast_szd(path, timeout=10)
                k = s // 1024
                if k > threshold:
                    items.append({
                        "n": name, "p": path, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{name.lower()}",
                        "risk": "none", "prio": 2, "cat": "dev"
                    })
        
        # IDE caches
        ide_caches = [
            ("JetBrains Cache", os.path.join(HOME, "AppData\\Local\\JetBrains"), 1048576),
            ("VS Code Cache", os.path.join(HOME, "AppData\\Roaming\\Code\\Cache"), 102400),
        ]
        for name, path, threshold in ide_caches:
            if os.path.isdir(path):
                s = _fast_szd(path, timeout=10)
                k = s // 1024
                if k > threshold:
                    items.append({
                        "n": name, "p": path, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{name.lower()}",
                        "risk": "none", "prio": 2, "cat": "dev"
                    })
        
        # Cloud sync
        cloud_caches = [
            ("OneDrive Cache", os.path.join(HOME, "AppData\\Local\\OneDrive"), 1048576),
        ]
        for name, path, threshold in cloud_caches:
            if os.path.isdir(path):
                s = _fast_szd(path, timeout=10)
                k = s // 1024
                if k > threshold:
                    items.append({
                        "n": name, "p": path, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{name.lower()}",
                        "risk": "none", "prio": 2, "cat": "cloud"
                    })
        
        # Communication
        comm_caches = [
            ("Teams Cache", os.path.join(HOME, "AppData\\Local\\Microsoft\\Teams\\cache"), 102400),
            ("Zoom Cache", os.path.join(HOME, "AppData\\Roaming\\Zoom\\bin\\cache"), 102400),
        ]
        for name, path, threshold in comm_caches:
            if os.path.isdir(path):
                s = _fast_szd(path, timeout=10)
                k = s // 1024
                if k > threshold:
                    items.append({
                        "n": name, "p": path, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{name.lower()}",
                        "risk": "none", "prio": 2, "cat": "chat"
                    })
        
        # Gaming
        gaming_caches = [
            ("Steam Shaders", os.path.join(HOME, "AppData\\Local\\Steam\\shader_cache"), 1048576),
        ]
        for name, path, threshold in gaming_caches:
            if os.path.isdir(path):
                s = _fast_szd(path, timeout=10)
                k = s // 1024
                if k > threshold:
                    items.append({
                        "n": name, "p": path, "k": k, "h": hk(k),
                        "safe": True, "reason": f"{name.lower()}",
                        "risk": "none", "prio": 2, "cat": "gaming"
                    })
        
        # Windows.old
        win_old = os.path.join(SYSROOT.replace("\\Windows", ""), "Windows.old")
        if os.path.isdir(win_old):
            s = szd(win_old, 2, 15)
            k = s // 1024
            if k > 1048576:
                items.append({
                    "n": "Windows.old", "p": win_old, "k": k, "h": hk(k),
                    "safe": True, "reason": "Previous Windows installation",
                    "risk": "none", "prio": 1, "cat": "system"
                })
    
    items.sort(key=lambda x: x["k"], reverse=True)
    return items

def find_dupes(min_mb=50):
    """Find duplicate files using size pre-filter + SHA256 + byte-level verify."""
    import hashlib
    import filecmp
    from collections import defaultdict
    
    paths = [HOME]
    if IS_WIN:
        for letter in ("D", "E"):
            if os.path.exists(f"{letter}:\\"):
                paths.append(f"{letter}:\\")
    
    min_sz = min_mb * 1024 * 1024
    size_groups = defaultdict(list)
    deadline = time.time() + 120
    
    def _scan(path):
        try:
            for entry in os.scandir(path):
                if time.time() > deadline:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        if size >= min_sz:
                            size_groups[size].append(entry.path)
                    elif entry.is_dir(follow_symlinks=False) and entry.name not in {".git", "node_modules", "__pycache__"}:
                        _scan(entry.path)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
    
    for p in paths:
        if os.path.exists(p):
            _scan(p)
    
    # Pre-filter: only hash files with same size
    candidates = {s: files for s, files in size_groups.items() if len(files) >= 2}
    
    # Hash candidates
    hash_groups = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_hash_file, fp): fp for files in candidates.values() for fp in files}
        for fut in as_completed(futs):
            fp = futs[fut]
            hv = fut.result()
            if hv:
                hash_groups[hv].append(fp)
    
    # Byte-level verify
    dupes = []
    for hv, files in hash_groups.items():
        if len(files) < 2:
            continue
        valid_groups = []
        remaining = list(files)
        while remaining:
            base = remaining.pop(0)
            group = [base]
            i = 0
            while i < len(remaining):
                if filecmp.cmp(base, remaining[i], shallow=False):
                    group.append(remaining.pop(i))
                else:
                    i += 1
            if len(group) >= 2:
                valid_groups.append(group)
        
        for group in valid_groups:
            fm = [(f, os.path.getmtime(f)) for f in group]
            try:
                fm.sort(key=lambda x: x[1], reverse=True)
            except (ValueError, TypeError):
                pass
            dupes.append({
                "keep": fm[0][0],
                "dups": [f[0] for f in fm[1:]],
                "cnt": len(group),
                "sz": hk(szf(fm[0][0]) // 1024),
                "wasted": hk(szf(fm[0][0]) * (len(group) - 1) // 1024)
            })
    
    dupes.sort(key=lambda x: len(x["dups"]), reverse=True)
    return dupes[:15]


def _hash_file(path):
    """Hash first 1MB of file using SHA256."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(1024 * 1024))
        return h.hexdigest()
    except (PermissionError, OSError):
        return None
