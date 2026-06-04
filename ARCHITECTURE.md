# Storage Analyzer v6 ¡ª Complete Architecture & Design Document

> For AI review: identify security vulnerabilities, performance bottlenecks, architectural flaws, and optimization opportunities.

## 1. System Overview

**Purpose**: Local disk storage analyzer and cleanup tool for Windows/macOS/Linux.
**Language**: Python 3.11, zero external dependencies (stdlib only).
**Size**: ~160KB total, 19 files.
**Core**: Single `engine.py` (676 lines) handles everything.

### Current Capabilities
- Multi-disk scanning (C/D/E drives, Linux mounts)
- System file detection (MEMORY.DMP, WinSxS, browser cache, etc.)
- Rule-based classification (green/red/yellow tiers from config.json)
- Duplicate file detection (SHA256 + byte-level verify)
- Incremental scan cache (skip unchanged dirs)
- History-based forecast (linear regression)
- Deletion with audit log + undo backup
- Interactive HTML report via local HTTP server
- DISM integration for WinSxS cleanup

## 2. Architecture

```
storage-analyzer/
©À©¤©¤ engine.py          29.8KB  Core engine (all logic)
©À©¤©¤ run.py              3.7KB  Entry point (direct import, summary output)
©À©¤©¤ config.json         2.1KB  Rules + protected paths
©À©¤©¤ ARCHITECTURE.md     This file
©À©¤©¤ assets/
©¦   ©À©¤©¤ report_template.html           25.8KB
©¦   ©¸©¤©¤ report_template_enhanced.html  19.8KB
©¸©¤©¤ scripts/
    ©À©¤©¤ utils.py         18.1KB  Shared utilities (disk, platform, cache)
    ©À©¤©¤ test.py          15.2KB  Test suite (30 tests)
    ©À©¤©¤ server.py         7.5KB  HTTP delete server (localhost only)
    ©À©¤©¤ compare.py        8.7KB  Scan comparison
    ©À©¤©¤ file_type_analyzer.py  8KB  File type stats
    ©À©¤©¤ old_files.py      7.8KB  Old file detection
    ©À©¤©¤ trend.py          5.8KB  Trend analysis
    ©À©¤©¤ build_report.py   1.7KB  HTML report generator
    ©À©¤©¤ classify.py       0.9KB  ¡ú thin wrapper, imports engine
    ©À©¤©¤ recommend.py      0.8KB  ¡ú thin wrapper, imports engine
    ©À©¤©¤ scan_hybrid.py    0.7KB  ¡ú thin wrapper, imports engine
    ©¸©¤©¤ duplicates.py     0.6KB  ¡ú thin wrapper, imports engine
```

### Data Flow

```
run.py
  ©¦
  ©À©¤ direct import ©¤©¤¡ú engine.main()
  ©¦                      ©¦
  ©¦                      ©À©¤ disks()           ¡ú {C:{t,u,f,p}, D:{...}}
  ©¦                      ©À©¤ scan_all()        ¡ú {temp:[], downloads:[], ...}
  ©¦                      ©À©¤ scan_sys()        ¡ú [MEMORY.DMP, WinSxS, ...]
  ©¦                      ©À©¤ gen_actions()     ¡ú [{act,what,path,sz,risk}, ...]
  ©¦                      ©À©¤ find_dupes()      ¡ú [{keep,dups,cnt,sz}, ...]
  ©¦                      ©À©¤ forecast()        ¡ú [{disk,lvl,msg}, ...]
  ©¦                      ©¦
  ©¦                      ©¸©¤ if --execute:
  ©¦                           ©À©¤ _safe_delete() for each safe item
  ©¦                           ©À©¤ _audit_log()  ¡ú deletions.log
  ©¦                           ©¸©¤ _undo_backup() ¡ú undo_backup/
  ©¦
  ©¸©¤ output: summary text (default) or JSON (--json flag)
```

## 3. Key Functions (engine.py)

| Function | Lines | Purpose |
|----------|-------|---------|
| `scan_all()` | 174-184 | Scan user directories (temp, downloads, etc.) |
| `scan_sys()` | 186-308 | Scan system files (MEMORY.DMP, WinSxS, browsers, VMs) |
| `_classify_item()` | 309-333 | Classify item as green/red/yellow using config rules |
| `gen_actions()` | 335-371 | Generate action list from scan results |
| `find_dupes()` | 373-419 | Find duplicate files (size¡úhash¡úbyte verify) |
| `forecast()` | 429-457 | Predict disk full date via linear regression |
| `_safe_delete()` | 538-583 | Delete with protection checks, DISM, recycle bin |
| `_audit_log()` | 514-522 | Persist deletion records to log file |
| `_undo_backup()` | 524-536 | Move files to backup before delete |

## 4. Security Model

### Protections
- **Dry-run default**: `--execute` flag required for actual deletion
- **Protected paths**: `config.json` whitelist (C:\Windows, /bin, etc.)
- **Core protected**: Hardcoded System32, Program Files, /etc, /usr
- **Force flag**: `scan_sys()` safe items bypass protection (MEMORY.DMP, WinSxS)
- **Audit log**: All deletions logged to `~/.cache/storage-analyzer/deletions.log`
- **Undo backup**: Optional pre-delete backup

### server.py Security
- Binds `127.0.0.1` only (no network exposure)
- Random 256-bit token per session
- Host header verification (blocks DNS rebinding)
- Path canonicalization via `os.path.realpath()`
- Allowlist-based access control

### Known Security Gaps
1. **No input sanitization on config.json**: Malicious rules could mark system files as green
2. **Race condition**: File state can change between scan and delete
3. **TOCTOU**: `_is_protected()` check and actual delete are not atomic
4. **No rollback for DISM**: DISM cleanup cannot be undone
5. **Audit log not tamper-proof**: Can be modified after deletion

## 5. Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Scan (cold) | ~7s | Full directory traversal |
| Scan (cached) | ~0.3s | Skip unchanged dirs via mtime cache |
| Duplicate detection | ~60s+ | Scans all drives, I/O bound |
| Classification | <10ms | Regex matching against config rules |
| Deletion | Variable | Depends on file count and locks |

### Performance Gaps
1. **No parallel disk scanning**: Each drive scanned sequentially
2. **Duplicate detection scans entire drives**: No incremental support
3. **szd() is single-threaded**: Directory size calculation is sequential
4. **No I/O throttling**: Can cause I/O storm on HDD
5. **Config reloaded on every import**: No caching of parsed rules

## 6. Configuration (config.json)

```json
{
  "scan": {"timeout": 30, "max_depth": 4, "min_kb": 51200, "workers": 6},
  "protected_paths": ["C:\\Windows", "C:\\Windows\\System32", ...],
  "classify": {
    "green": [{"pat": "regex", "reason": "text", "conf": "hi|med|low"}],
    "red": [{"pat": "regex", "reason": "text", "conf": "hi"}],
    "known_apps": {"name": ["tier", "reason"]}
  }
}
```

**Issue**: `workers` config is defined but never used.

## 7. Test Coverage

- 30 tests covering: utils, scan, classify, duplicates, recommend, config, report, file types, old files, deep scanner
- All pass on Windows 10, Python 3.11
- **Gaps**: No tests for `_safe_delete()`, `_audit_log()`, `forecast()`, `DISM`, `Recycle Bin`

## 8. Known Bugs & Issues

1. **`--execute` was non-functional**: Fixed in v6 (actually deletes now)
2. **Size calculation bug**: `hb(size // 1024)` was wrong (fixed)
3. **Locked files**: NVIDIA cache, CBS logs locked by running processes
4. **MEMORY.DMP requires admin**: Scheduled for reboot delete via MoveFileExW
5. **WinSxS size estimate**: `szd()` only samples top 2 levels, may underestimate

## 9. Optimization Opportunities

### Security
- [ ] Config.json schema validation (prevent malicious rules)
- [ ] Atomic delete (lock file ¡ú verify ¡ú delete)
- [ ] Signed audit log
- [ ] Sandbox server.py further (seccomp/AppArmor)

### Performance
- [ ] Parallel disk scanning with ThreadPoolExecutor
- [ ] Incremental duplicate detection (only scan changed files)
- [ ] I/O throttling for HDD (configurable max_workers)
- [ ] Cache parsed config rules

### Architecture
- [ ] Split engine.py into modules (scanner, classifier, deleter, forecaster)
- [ ] Plugin system for custom cleanup targets
- [ ] Event-driven architecture for progress reporting
- [ ] Proper logging framework (not just stderr print)

### Features
- [ ] Browser extension data cleanup (Chrome/Edge/Firefox profiles)
- [ ] Docker image pruning (docker system prune)
- [ ] npm/pip/yarn cache cleanup
- [ ] Windows.old detection and cleanup
- [ ] Scheduled cleanup (Windows Task Scheduler integration)
- [ ] GUI (tkinter/PyQt) or TUI (curses)

### Testing
- [ ] Add tests for deletion logic
- [ ] Add tests for DISM integration
- [ ] Add tests for Recycle Bin
- [ ] Mock filesystem for cross-platform testing
- [ ] Property-based testing for classification rules

## 10. Questions for Review

1. Is the single-file engine.py architecture sustainable at 676 lines?
2. Is the security model sufficient for a local cleanup tool?
3. Are there critical cleanup targets we're missing?
4. Is the config.json format extensible enough?
5. Should we add a plugin system for custom cleanup rules?
6. How should we handle the admin privilege requirement?
7. Is the incremental cache strategy correct (mtime-based)?
8. Should duplicate detection be async/lazy?

## 11. Dependencies

- **Python 3.8+** (uses walrus operator, f-strings)
- **No external packages** (stdlib only)
- **Optional**: ctypes (for Windows Shell API, Recycle Bin)
- **Optional**: DISM (for WinSxS cleanup)

## 12. Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | ? Full | Primary target, all features work |
| macOS | ?? Partial | plat_paths() defined but not tested |
| Linux | ?? Partial | Basic paths defined, no testing |
