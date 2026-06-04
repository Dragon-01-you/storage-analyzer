# Developing Storage Analyzer

A guide for contributors who want to:

1. Add a new **cleaner** (a new cleanup target).
2. Add a new **AI judge backend** (different LLM provider).
3. Add a new **CLI subcommand** (e.g. `sa doctor`, `sa config`).
4. Distribute your extension as a **plugin package** on PyPI.

---

## 1. Add a new cleaner

A cleaner is one Python class. One file. ~30-100 lines.

### Minimal example

```python
# cleaners/myapp.py
from cleaners._base import Cleaner, Entry, ScanContext


class MyAppCacheCleaner(Cleaner):
    name = "myapp-cache"
    platforms = ("windows", "macos", "linux")
    risk_level = "none"
    category = "dev"
    description = "MyApp local cache (auto-rebuilt)"

    def analyze(self, ctx: ScanContext) -> list[Entry]:
        # Build your path list per platform
        candidates = []
        if ctx.is_windows:
            candidates.append(ctx.home + r"\AppData\Local\MyApp\cache")
        elif ctx.is_macos:
            candidates.append(ctx.home + "/Library/Caches/MyApp")
        else:
            candidates.append(ctx.home + "/.cache/myapp")

        out = []
        for path in candidates:
            if not os.path.isdir(path):
                continue
            sz = sum_dir_size(path, max_depth=3)   # any helper you want
            if sz < 50 * 1024 * 1024:               # skip < 50MB
                continue
            out.append(Entry(
                name="MyApp Cache",
                path=path,
                size_kb=sz // 1024,
                size_h=human_kb(sz // 1024),
                reason="MyApp local cache (auto-rebuilt)",
                risk="none",
                prio=2,
                cat="dev",
                safe=True,           # eligible for one-click delete
            ))
        return out
```

### Register it

Open `cleaners/__init__.py` and add your class to `REGISTRY`:

```python
from .myapp import MyAppCacheCleaner

REGISTRY: List[type] = [
    *SYSTEM_CLEANERS,
    *BROWSER_CLEANERS,
    MyAppCacheCleaner,           # <-- add here
    ...
]
```

That's it. No other code change needed. The next `python run.py --deep` will pick it up.

### Required class attributes

| Attribute | Type | Example | Notes |
|---|---|---|---|
| `name` | str | `"myapp-cache"` | Unique. The registry enforces no duplicates. |
| `platforms` | tuple | `("windows", "macos", "linux")` | Empty tuple = never runs. |
| `risk_level` | str | `"none"` / `"med"` / `"high"` | Drives UI color + default action. |
| `category` | str | `"system"` / `"dev"` / `"browser"` / `"cloud"` / `"chat"` / `"ide"` / `"gaming"` / `"mail"` / `"vm"` | Used for `--include-vm` style filters. |
| `description` | str | `"MyApp local cache"` | Shown in HTML report. |

### Optional but recommended

- `requires_privilege = True` if it needs admin (UAC / sudo). Drives the privilege escalation workflow.
- `needs_recycle = True` for items that should go through Recycle Bin, not raw delete.
- `needs_dism = True` for items that need DISM (WinSxS etc.) — engine routes these to the proper protocol.

### Default `clean()` is fine for 90% of cases

`Cleaner.clean()` in the base class does the right thing: iterate entries, call `safe_delete()` with the right flags, write to audit log, return a `Result`. Override it only when you need a different protocol (e.g. `docker system prune`, `npm cache clean --force`).

### Testing

Drop a test in `tests/test_cleaners.py`:

```python
def test_myapp_cache_finds_cache(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    cache = home / "AppData" / "Local" / "MyApp" / "cache"
    touch(cache / "blob", size_mb=200)

    ctx = make_ctx(home, home, "windows")
    entries = MyAppCacheCleaner().analyze(ctx)
    assert len(entries) == 1
    assert "MyApp" in entries[0].name
```

Or rely on the **automatic** `test_cleaner_smoke` parametrized test that runs against every registered cleaner.

---

## 2. Add a new AI judge backend

The `BaseJudge` in `engine/classify/ai_judge.py` is one method:

```python
from engine.classify.ai_judge import BaseJudge, Verdict
import time

class OpenAIJudge(BaseJudge):
    def __init__(self, api_key, model="gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def judge(self, item: dict) -> Verdict:
        t0 = time.time()
        prompt = self._build_prompt(item)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content
        # Parse the same TIER|REASON|CONFIDENCE format
        return self._parse(text, self.model, int((time.time()-t0)*1000))
```

To plug in: extend `from_config()` in `ai_judge.py` to recognize your backend name in the `ai:` config block:

```json
{
  "ai": {
    "enabled": true,
    "backend": "openai",
    "api_key": "sk-...",
    "model": "gpt-4o-mini"
  }
}
```

---

## 3. Add a new CLI subcommand

`engine/main.py` is intentionally small. To add a `sa doctor` command:

```python
# In engine/main.py main()
if args.cmd == "doctor":
    return doctor_main()

# New function
def doctor_main():
    print("Running self-diagnostics...")
    # check Python version, config validity, registry loadable, etc.
```

And register an entry point in `pyproject.toml`:

```toml
[project.scripts]
sa = "engine.main:main"
sa-doctor = "engine.main:doctor_main"
```

---

## 4. Distribute as a plugin (3rd-party package)

You can publish a `my-storage-analyzer-plugin` to PyPI. Users install it and your cleaners auto-load.

**Your package:**

```
my-sa-plugin/
├── pyproject.toml
└── src/my_sa_plugin/
    ├── __init__.py
    └── my_cleaner.py
```

**`pyproject.toml`:**

```toml
[project]
name = "my-sa-plugin"
version = "0.1.0"
dependencies = ["storage-analyzer>=7.1"]

[project.entry-points."storage_analyzer.cleaners"]
my_cleaner = "my_sa_plugin.my_cleaner:MyCleaner"
```

**`my_cleaner.py`:** identical to Section 1. The only difference is your class lives outside `storage_analyzer/cleaners/`.

When a user runs `pip install my-sa-plugin`, the registry is auto-extended and your cleaner shows up in the next scan. No fork, no PR to upstream.

---

## 5. Architecture cheat sheet

```
storage-analyzer/
├── engine/                # Core engine (importable, no side effects)
│   ├── main.py            # CLI + run() entry
│   ├── scanner.py         # Legacy: hand-coded scan_sys()
│   ├── scanner_v2.py      # Modern: delegates to cleaners
│   ├── classifier.py      # Regex/heuristic classifier
│   ├── classify/
│   │   └── ai_judge.py    # Optional LLM judge
│   ├── deleter.py         # Atomic delete + DISM + Recycle
│   ├── forecaster.py      # Linear regression trend
│   └── utils.py           # hb/hk/szd/log
├── cleaners/              # Plugin pipeline (default since v7.1)
│   ├── _base.py           # Cleaner / Entry / Result / ScanContext
│   ├── _system.py         # Windows system
│   ├── _browsers.py       # Chrome/Edge/FF/Brave
│   ├── _dev.py            # npm/pip/cargo/...
│   ├── _ide.py            # VSCode/JetBrains
│   ├── _cloud_chat.py     # OneDrive/Teams/Zoom
│   ├── _vmware.py         # VMware VM detect + advisory
│   ├── _extras.py         # GPU/Docker/WeChat/Tencent/DingTalk
│   ├── _legacy_adapter.py # Entry -> legacy dict shape
│   └── __init__.py        # REGISTRY + run_all()
├── scripts/               # CLI helpers (snapshot, drill, etc.)
├── tests/                 # pytest suite (44 tests)
├── assets/                # HTML report templates
├── __main__.py            # zipapp entry
├── run.py                 # dev entry (import engine package)
├── config.json            # rules + protected paths
├── SKILL.md               # AI agent handbook
├── DEVELOPING.md          # <-- you are here
└── pyproject.toml         # PEP 517 build + entry points
```

---

## 6. Style guide

- **One cleaner = one file** (unless trivially small like `_system.py`).
- **Always include `description`** — it's the only user-facing string.
- **Use `ctx.is_windows` etc.** — never `os.name == "nt"` directly.
- **Default `clean()`** — only override for non-trivial protocols.
- **Test with `tmp_path`** — never depend on the real filesystem in tests.
- **No print()** — use `engine.utils.log(msg, lvl)` (goes to stderr).
- **Failures must be loud** — `raise` from analyze(); the runner catches per-cleaner so one bad plugin doesn't kill the scan.

---

## 7. Release checklist

- [ ] `python -m pytest tests/` → 44+ pass
- [ ] `python scripts/test.py --all` → 42/42 pass (legacy)
- [ ] `python scripts/build_zipapp.py && python scripts/verify_zipapp.py` → OK
- [ ] `python scripts/compare_scanners.py` → modern ≥ legacy
- [ ] Bump `version` in `pyproject.toml`
- [ ] Tag in git: `git tag v7.1.0`
- [ ] (optional) `python -m build` → upload to PyPI

---

## 8. License

MIT. See LICENSE.
