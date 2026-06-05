# Flow: Install Storage Analyzer as Agent Skill

This flow installs Storage Analyzer into a project or user-level Claude Code environment.

## Step 1: Check Prerequisites

```bash
python --version 2>/dev/null || python3 --version 2>/dev/null
pip --version 2>/dev/null
git --version 2>/dev/null
```

## Step 2: Choose Installation Method

Ask the user:

1. **pip install** (recommended) - `pip install storage-analyzer`
2. **Git clone** - Full source with examples
3. **Download SKILL.md only** - Just the skill definition, no code

## Step 3: Install

### Method A: pip
```bash
pip install storage-analyzer
```
Verify:
```bash
python -c "import v8; print(v8.__version__)"
```

### Method B: Git Clone
```bash
git clone https://github.com/Dragon-01-you/storage-analyzer.git
cd storage-analyzer
pip install -e .
```

### Method C: SKILL.md Only
Download just the SKILL.md for reference:
```bash
curl -fsSL https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main/SKILL.md \
  -o ~/.claude/skills/storage-analyzer/SKILL.md
```

## Step 4: Create Agent Configuration

Create `.claude/agents/storage-analyzer.md`:

```yaml
---
name: storage-analyzer
description: "Use this agent when the user asks about disk space, storage usage, finding large files, detecting duplicates, or cleaning up disk space. For example: 'What's using my disk space?', 'Find duplicate files', 'Help me clean up my C: drive'"
model: sonnet
tools: Read, Bash, Glob, Grep, AskUserQuestion
---

You are a disk storage analysis expert specializing in identifying wasted space and safely cleaning up unnecessary files.

## Your Expertise

- Cross-platform disk analysis (Windows, macOS, Linux)
- File categorization by type, age, and risk level
- Duplicate detection using multi-stage hashing
- Safe cleanup with 5-layer protection model

## How You Work

1. **Scan first** - Always analyze before suggesting changes
2. **Show, don't delete** - Present findings, ask for confirmation
3. **Risk-rated** - Every item gets a risk level (SAFE/REVIEW/KEEP)
4. **Audit trail** - All operations logged with SHA-256 integrity

## Commands

```bash
# Analyze (dry-run, no changes)
python run.py --deep --json -o scan.json

# Find duplicates
python run.py --dupes

# Generate report
python run.py --deep --report

# Execute cleanup (requires confirmation)
python run.py --execute
```

## Safety Rules

- NEVER delete without user confirmation
- System directories are hard-blocked
- User profile requires explicit approval
- Default to dry-run mode
```

## Step 5: Create Workflow Skill

Create `.claude/skills/disk-cleanup/SKILL.md`:

```yaml
---
name: disk-cleanup
description: "Analyze and clean disk storage. Use when user asks about disk space or cleanup."
user-invocable: true
allowed-tools: Bash, Read, Grep, AskUserQuestion
context: fork
---

Analyze disk usage for the user and provide cleanup recommendations.

Target path: $ARGUMENTS (default: current directory)

1. Run: python run.py --deep --json -o scan.json
2. Read scan.json
3. Present top cleanable items with sizes and risk levels
4. Ask user which items to clean
5. Only execute if user confirms
```

## Step 6: Verify

```bash
# Check installation
python -c "from v8 import __version__; print(f'Storage Analyzer {__version__}')"

# Quick test scan
python run.py --help
```

## Summary

After installation:
- `/storage-analyzer [path]` - Run analysis
- `/disk-cleanup [path]` - Full cleanup workflow
- Storage Analyzer agent auto-delegates when disk topics arise
- GitHub: https://github.com/Dragon-01-you/storage-analyzer
