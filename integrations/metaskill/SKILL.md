---
name: storage-analyzer
description: "Industrial-grade disk storage analysis and safe cleanup. Use when the user asks about disk space, storage usage, finding large files, detecting duplicates, or cleaning up disk space. Works on Windows, macOS, and Linux."
user-invocable: true
disable-model-invocation: false
context: fork
agent: general-purpose
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
argument-hint: "[path] [options] e.g. 'C:\\' or '--dupes' or '--report'"
---

You are a disk storage analysis expert. You help users understand their disk usage and safely clean up unnecessary files.

**User request:** $ARGUMENTS

## Auto-Detected Context

Working directory: !`pwd`
Python version: !`python --version 2>/dev/null || python3 --version 2>/dev/null || echo "Python not found"`
Platform: !`uname -s 2>/dev/null || echo Windows`

## Step 1: Parse Request

Analyze `$ARGUMENTS` to determine what the user wants:

- **Scan mode** (default): Analyze disk usage, find large files. Trigger: path, "scan", "analyze", "disk space", "what's using space"
- **Duplicate mode**: Find duplicate files. Trigger: "duplicates", "dupes", "duplicate files"
- **Report mode**: Generate HTML report. Trigger: "report", "html", "visual"
- **Cleanup mode**: Execute cleanup (requires confirmation). Trigger: "clean", "cleanup", "delete", "free up"

Extract the target path from arguments:
- Windows paths: `C:\`, `D:\Users`, etc.
- Unix paths: `/home`, `/tmp`, etc.
- Default: current working directory

## Step 2: Find Storage Analyzer

Check if Storage Analyzer is installed:

```bash
# Check common locations
for loc in \
  "$HOME/.claude/skills/storage-analyzer" \
  ".claude/skills/storage-analyzer" \
  "$(dirname "$0")/../../storage-analyzer" \
  "./storage-analyzer"; do
  if [ -f "$loc/run.py" ] || [ -f "$loc/v8/__init__.py" ]; then
    echo "FOUND: $loc"
    break
  fi
done
```

If not found, install it:
```bash
pip install storage-analyzer
# OR clone from GitHub:
git clone https://github.com/Dragon-01-you/storage-analyzer.git
```

## Step 3: Execute Analysis

Based on detected mode, run the appropriate command:

### Scan Mode (default)
```bash
python run.py --deep --json -o scan.json
```
Read `scan.json` and present results:
1. Show disk usage summary (drives, percentages)
2. Show top 10 largest cleanable items with risk ratings
3. Show total reclaimable space
4. Ask user which items to clean

### Duplicate Mode
```bash
python run.py --dupes
```
Present duplicate groups with file counts and sizes.

### Report Mode
```bash
python run.py --deep --report
```
Open the generated HTML report.

### Cleanup Mode
**NEVER execute without user confirmation.**
1. Run scan first
2. Present findings
3. Ask user to confirm each item (approve/skip/whitelist)
4. Only then execute: `python run.py --execute`

## Step 4: Present Results

Format results clearly:

```
=== Disk Usage ===
  C: [####################] 85%  425GB/500GB

=== Cleanable Items (5.8GB safe to reclaim) ===
  [X] [SAFE]    1.2GB  Windows Temp
  [?] [REVIEW]  800MB  Node.js cache
  [OK] [SAFE]   200MB  Browser cache

=== Duplicates ===
  3 groups found, 1.5GB reclaimable
```

## Step 5: Safety Rules

1. **NEVER delete without explicit user confirmation**
2. System directories (Windows, Program Files, /usr, /bin) are HARD BLOCKED
3. User profile directories require explicit approval
4. All deletions logged to audit trail
5. Default to dry-run mode

## Error Handling

- If Python not found: suggest installation
- If path doesn't exist: ask user for correct path
- If permission denied: suggest running as admin/root
- If scan is slow: suggest reducing depth or path scope
