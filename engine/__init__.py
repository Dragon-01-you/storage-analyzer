"""Storage Analyzer Engine - Modular Architecture.

This package provides a modular storage analysis and cleanup engine.
"""
from .utils import (
    HOME, IS_WIN, IS_MAC, IS_LINUX, SYSROOT, PP, CFG, PROTECTED,
    hb, hk, log, szf, szd, _fast_szd, disks, plat_paths,
    load_scan_cache, save_scan_cache, load_history, save_history, audit_log,
    CACHE_DIR, SCAN_CACHE_FILE, HISTORY_FILE, AUDIT_LOG,
    _ensure_cache_dir
)
from .scanner import scan_all, scan_sys, scan_dir, find_dupes, _hash_file
from .scanner_v2 import scan_sys_v2
from . import classify  # subpackage: classifier + ai_judge
classify_item = classify.classify_item
gen_actions = classify.gen_actions
_parse_h = classify._parse_h
from .deleter import safe_delete, atomic_delete, _is_protected
from .forecaster import forecast


# Backward compatibility aliases
_classify_item = classify_item
_hash = _hash_file if '_hash_file' in dir() else None
_audit_log = audit_log
_save_history = save_history
_load_history = load_history

__version__ = "7.0.0"
__all__ = [
    # Utils
    'HOME', 'IS_WIN', 'IS_MAC', 'IS_LINUX', 'SYSROOT', 'PP', 'CFG', 'PROTECTED',
    'hb', 'hk', 'log', 'szf', 'szd', '_fast_szd', 'disks', 'plat_paths',
    'load_scan_cache', 'save_scan_cache', 'load_history', 'save_history', 'audit_log',
    'CACHE_DIR', 'SCAN_CACHE_FILE', 'HISTORY_FILE', 'AUDIT_LOG',
    '_ensure_cache_dir',
    # Scanner
    'scan_all', 'scan_sys', 'scan_dir', 'find_dupes', 'scan_sys_v2',
    # Classifier
    'classify_item', 'gen_actions', '_parse_h', 'classify',
    # Deleter
    'safe_delete', 'atomic_delete', '_is_protected',
    # Forecaster
    'forecast',
    # Backward compat
    '_classify_item', '_hash', '_audit_log', '_save_history', '_load_history'
]
