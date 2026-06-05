# Storage Analyzer

> **Local AI-driven disk storage analyzer and safe cleanup tool.**
> Cross-platform (Windows / macOS / Linux), zero external dependencies, plugin-extensible.

```
✓ 30+ cleanup targets, all data-driven (no hard-coded rules in the engine)
✓ Dry-run by default, --execute to actually clean
✓ 86 tests, 0 external dependencies, ships as a single 320KB .pyz
✓ Built for tool-builders: AI-agent-readable (SKILL.md), plugin-extensible (entry_points)
```

---

## Quick start

```bash
# Drop-in single-file bundle (no install needed)
python storage-analyzer.pyz --deep

# Dry-run analysis + human summary
python run.py

# Full deep scan (Windows temp / CBS logs / WinSxS / browsers / dev caches)
python run.py --deep

# Machine-readable JSON
python run.py --deep --json -o scan.json

# Find duplicate files >= 50MB
python run.py --dupes

# HTML report
python run.py --deep --report

# ACTUALLY delete (dry-run OFF)
python run.py --deep --execute
```

---

## Install (developer mode)

```bash
git clone <repo>
cd storage-analyzer
pip install -e .              # installs the `sa` command
sa --deep                      # same UX as the zipapp
```

---

## What gets scanned

| Category | Cleaners | Examples |
|---|---|---|
| System | 9 | MEMORY.DMP, CBS Logs, WinSxS (DISM), Prefetch, Thumbnail cache, Recycle Bin, Windows.old |
| GPU | 1 | NVIDIA / AMD / Intel shader cache |
| Browsers | 4 + 1 profile | Chrome / Edge / Firefox / Brave cache; full profile (advisory) |
| Dev tools | 6 + 1 | npm / yarn / pnpm / pip / cargo / Gradle/Maven/NuGet; Docker |
| IDE | 2 | VSCode / JetBrains |
| Cloud + Chat | 3 + 3 | OneDrive / Teams / Zoom; WeChat / Tencent / DingTalk |
| VMs | 1 (advisory) | VMware Workstation (snapshot merge advice, no auto-delete) |

**Total: 30+ built-in cleaners, each is one Python file in `cleaners/`.**

---

## Command-line reference

```text
python run.py [options]

Options:
  --execute         Actually delete files (default: dry-run)
  --quiet           Suppress stderr logs
  --deep            Include system scan
  --dupes           Find duplicate files (>= 50MB)
  --full            --deep + --dupes
  --include-vm      Surface VMware / VM items in the deep scan
  --legacy-scanner  Use the legacy hand-coded scan_sys() instead of the plugin pipeline
  --no-cache        Skip incremental cache
  -o, --output FILE Write JSON to file
  --json            Print JSON to stdout (default)
  --report          Generate HTML report + open in browser
```

---

## Output shape (JSON)

```json
{
  "ok": true,
  "elapsed": 19.5,
  "dry_run": true,
  "disks": {
    "C": {"t": 299000000000, "u": ..., "f": ..., "p": 72.8, "uh": "...", "fh": "..."}
  },
  "safe_h": "28GB",
  "actions": [
    {
      "act": "delete",       // or "review" / "keep"
      "what": "System memory dump",
      "path": "C:\\Windows\\MEMORY.DMP",
      "sz":  "15GB",
      "risk": "none",        // or "med" / "high"
      "prio": 1,
      "cat":  "system"
    }
  ],
  "dupes":     [...],   // when --dupes
  "warnings":  [...]    // trend warnings
}
```

---

## Safety

| Layer | Default | Override |
|---|---|---|
| Dry-run | **ON** | `--execute` flips it |
| Protected paths | Hardcoded + `config.json` whitelist | None (cannot be disabled) |
| Core paths (System32, /usr, /etc) | **NEVER delete** | None |
| Audit log | Every action logged to `~/.cache/storage-analyzer/deletions.log` | N/A |
| Recycle Bin | Default deletion target on Windows | Engine handles it via `SHFileOperation` |

---

## Configuration (`config.json`)

```json
{
  "scan": {"timeout": 30, "max_depth": 4, "min_kb": 51200, "workers": 6},
  "protected_paths": [
    "C:\\Windows", "C:\\Program Files", "/bin", "/etc", "/usr", "/System"
  ],
  "classify": {
    "green": [{"pat": "(?i)\\\\Temp\\\\?", "reason": "Windows temp", "conf": "hi"}],
    "red":   [{"pat": "(?i)\\\\Windows\\\\", "reason": "System files", "conf": "hi"}],
    "known_apps": {"docker": ["yellow", "Docker data"]}
  },
  "ai": {
    "enabled": false,
    "endpoint": "http://localhost:11434",
    "model": "qwen2.5:3b"
  }
}
```

---

## For AI agents

This repo includes a [`SKILL.md`](SKILL.md) at the project root.
Any agent that reads SKILL.md (Claude Code, Cursor, Continue, Mavis) can drive this tool end-to-end.

Quick commands an agent will see:

```bash
# Full analysis
python run.py --deep --json -o scan.json

# Modify scan.json's actions[].risk / act, then re-execute
python run.py --execute -o actions.json
```

---

## For developers / contributors

See [`DEVELOPING.md`](DEVELOPING.md) for the full guide.

TL;DR:
- **Add a cleaner** → drop a class in `cleaners/my_app.py`, register in `cleaners/__init__.py` REGISTRY.
- **Add a CLI command** → argparse in `engine/main.py`.
- **Distribute as a plugin** → publish a PyPI package with `entry_points` under `storage_analyzer.cleaners`.

---

## Architecture

```
storage-analyzer/
├── engine/                # Core engine (importable, no side effects)
├── cleaners/              # Plugin pipeline (default since v7.1)
├── v8/                    # Next-gen modules (types, safeguard, audit, ...)
├── scripts/               # CLI helpers (snapshot, drill, compare, ...)
├── tests/                 # pytest suite (75 tests)
├── assets/                # HTML report templates
├── __main__.py            # zipapp entry
├── run.py                 # dev entry (import engine package)
├── config.json            # rules + protected paths
├── SKILL.md               # AI agent handbook (universal)
├── DEVELOPING.md          # Contributor guide
├── pyproject.toml         # PEP 517 build + entry points
└── storage-analyzer.pyz   # Single-file bundle (built)
```

---

## Testing

```bash
# pytest (44 tests, ~24s)
python -m pytest tests/

# legacy framework (42 tests, ~100s on full scan)
python scripts/test.py --all

# verify the zipapp works
python scripts/build_zipapp.py
python scripts/verify_zipapp.py
```

---

## Performance

| Operation | Time | Notes |
|---|---|---|
| Scan (cold, full disk) | ~20s | First run on Windows 10, ~700K files |
| Scan (cached) | ~0.3s | Incremental mtime cache |
| Duplicate detection | ~60s+ | All drives, I/O bound |
| Classification | <10ms | Regex against config rules |
| AI judge (Ollama qwen2.5:3b) | ~50ms/item | Cached, 5s timeout, falls back to rules |

---

## License

MIT
