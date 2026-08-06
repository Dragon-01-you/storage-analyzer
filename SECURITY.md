# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 9.0.x   | :white_check_mark: |
| < 9.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** open a public issue
2. Email: [your-email@example.com] (replace with your email)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Features

Storage Analyzer includes multiple security layers:

### 1. Protected Paths
System directories are hardcoded and cannot be deleted:
- Windows: `C:\Windows`, `C:\Program Files`, etc.
- macOS: `/System`, `/Applications`, `/usr`, etc.
- Linux: `/`, `/bin`, `/sbin`, `/etc`, `/boot`, etc.

### 2. Dry-run Mode
- Default mode only scans, never deletes
- Must explicitly use `--execute` to delete files

### 3. Confidence Tiers
- SAFE: Definitely deletable
- RECOMMENDED: Very likely safe
- SUGGESTED: Needs review
- ASK: Only you know

### 4. Audit Logging
All deletions are logged to `~/.cache/storage-analyzer/audit.jsonl`

### 5. User Confirmation
- Always asks for confirmation before deleting
- Shows exactly what will be deleted
- Cannot be bypassed

## Best Practices

1. Always review scan results before executing
2. Start with `--friendly` mode for easy understanding
3. Use `--confidence` to see risk levels
4. Keep backups of important files
5. Run as administrator only when necessary
