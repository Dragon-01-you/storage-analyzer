---
name: storage-analyzer
description: "Analyze disk storage usage, identify large files and directories, detect duplicates, and generate cleanup recommendations. Trigger when user asks about disk space, storage usage, disk cleanup, finding large files, or freeing up space."
provenance:
  origin: opensquilla-original
  license: MIT
  upstream_url: https://github.com/Dragon-01-you/storage-analyzer
  maintained_by: Dragon-01-you
version: 8.1.0
metadata:
  platform:
    emoji: "\U0001F4C0"
    requires:
      anyBins: ["python", "python3"]
    os: ["windows", "linux", "darwin"]
  opensquilla:
    risk_level: "low"
    capabilities: ["filesystem"]
  tags: ["disk", "storage", "cleanup", "duplicates", "analysis"]
entrypoint:
  command: python {baseDir}/scripts/analyze.py
  args:
    - --path
    - "{{ with.path | default('.') }}"
    - --depth
    - "{{ with.depth | default(3) }}"
    - --min-size
    - "{{ with.min_size | default('100MB') }}"
    - --mode
    - "{{ with.mode | default('scan') }}"
  parse: json
  timeout: 120
---

# Storage Analyzer

Industrial-grade disk storage analysis and safe cleanup tool. Cross-platform (Windows/macOS/Linux), zero external dependencies.

## What It Does

1. **Scan** - Recursively analyzes directories, categorizes files by type/age/risk
2. **Detect duplicates** - 3-stage duplicate detection (size → hash → content)
3. **Recommend** - Generates safe cleanup proposals with risk ratings
4. **Execute** - Performs cleanup with 5-layer safety model (always needs user confirmation)

## Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | `.` | Directory path to analyze |
| `depth` | int | `3` | Scan depth (1-10) |
| `min_size` | string | `100MB` | Minimum file size to report (e.g., `50MB`, `1GB`) |
| `mode` | string | `scan` | Operation mode: `scan`, `dupes`, `report` |

## Output Format (JSON)

```json
{
  "ok": true,
  "mode": "scan",
  "dry_run": true,
  "disks": {
    "C:": {"p": 75, "uh": "200GB", "th": "500GB"}
  },
  "actions": [
    {"act": "delete", "risk": "SAFE", "sz": "1.2GB", "what": "Windows Temp", "path": "C:\\Windows\\Temp"}
  ],
  "safe_total": "5.8GB",
  "elapsed": 2.3
}
```

## Modes

- **scan** (default): Full analysis with cleanup recommendations
- **dupes**: Duplicate file detection only
- **report**: Generate HTML report

## Safety Model

- Default: **dry-run only** (no files deleted)
- Protected paths: System directories, user profile, program files are hard-blocked
- Deletion requires explicit `execute` mode + user confirmation
- All operations logged to audit trail with SHA-256 integrity

## Requirements

- Python 3.10+
- No external dependencies for basic scan
- `pydantic>=2.0` recommended (included in pip install)
- Cross-platform: Windows, macOS, Linux
