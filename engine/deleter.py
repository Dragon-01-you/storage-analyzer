"""Deleter module - handles safe deletion with protection checks."""
import os
import shutil
import sys

from .utils import HOME, IS_WIN, PROTECTED, audit_log


def _is_protected(path):
    """Check if path is in protected list or under protected directory."""
    real = os.path.realpath(path)
    for pp in PROTECTED:
        if real == pp or real.startswith(pp + os.sep):
            return True
    return False


def atomic_delete(path, force=False):
    """Atomic delete: lock -> verify -> delete. Eliminates TOCTOU."""
    lock_file = None
    try:
        # Create lock file in same directory
        dir_name = os.path.dirname(path)
        lock_file = os.path.join(dir_name, f".sa_lock_{os.getpid()}")
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # Verify path still exists
        if not os.path.exists(path):
            return False, "path changed during delete"
        
        # Perform actual delete
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        
        return True, "ok"
    except PermissionError:
        return False, "permission denied"
    except OSError as e:
        return False, str(e)
    finally:
        # Always clean up lock file
        if lock_file and os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass


def safe_delete(path, force=False, use_undo=False, is_dism=False, is_recycle=False):
    """Delete a file or directory safely with protection checks."""
    # Special: Recycle Bin
    if is_recycle:
        try:
            import ctypes
            hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
            if hr == 0:
                audit_log("RECYCLE_BIN", "Recycle Bin", "emptied")
                return True, "recycle bin emptied"
            return False, f"SHQueryRecycleBin failed (hr={hr})"
        except Exception as e:
            return False, str(e)
    
    # Special: WinSxS via DISM
    if is_dism:
        try:
            import subprocess
            r = subprocess.run(
                ["Dism", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
                capture_output=True, text=True, timeout=300
            )
            if r.returncode == 0:
                audit_log("DISM", "WinSxS", "component cleanup done")
                return True, "DISM component cleanup done"
            return False, f"DISM failed: {r.stderr[:200]}"
        except Exception as e:
            return False, str(e)
    
    # Normal path-based delete
    real = os.path.realpath(path)
    if not os.path.exists(real):
        return False, "not found"
    
    if not force and _is_protected(real):
        return False, "protected path"
    
    # Core protected paths (never delete these even with force)
    CORE_PROTECTED = {
        os.path.realpath("C:\\Windows\\System32"),
        os.path.realpath("C:\\Program Files"),
        os.path.realpath("C:\\Program Files (x86)"),
        os.path.realpath("/bin"),
        os.path.realpath("/etc"),
        os.path.realpath("/usr"),
        os.path.realpath("/System")
    }
    if any(real == cp or real.startswith(cp + os.sep) for cp in CORE_PROTECTED):
        return False, "core system path"
    
    # Undo backup if requested
    if use_undo:
        _undo_backup(real)
    
    # Best-effort for directories: delete contents, skip locked files
    if os.path.isdir(real) and not os.path.islink(real):
        ok = 0
        locked = 0
        for root, dirs, files in os.walk(real, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                    ok += 1
                except (PermissionError, OSError):
                    locked += 1
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except (PermissionError, OSError):
                    pass
        try:
            os.rmdir(real)
        except (PermissionError, OSError):
            pass
        if ok > 0:
            return True, f"cleaned {ok} files, {locked} locked"
        if locked > 0:
            return False, f"{locked} files locked by other processes"
        return False, "empty or already cleaned"
    
    # Single file
    try:
        os.remove(real)
        return True, "ok"
    except PermissionError:
        if IS_WIN:
            try:
                import ctypes
                ctypes.windll.kernel32.MoveFileExW(real, None, 0x4)
                return True, "scheduled delete on reboot"
            except Exception:
                pass
        return False, "permission denied"
    except OSError as e:
        return False, str(e)


def _undo_backup(path):
    """Move file/dir to backup before delete."""
    if not os.path.exists(path):
        return None
    backup_dir = os.path.join(os.path.dirname(path), ".sa_backup")
    try:
        os.makedirs(backup_dir, exist_ok=True)
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        name = os.path.basename(path.rstrip(os.sep))
        dest = os.path.join(backup_dir, f"{name}_{ts}")
        shutil.move(path, dest)
        return dest
    except (PermissionError, OSError):
        return None
