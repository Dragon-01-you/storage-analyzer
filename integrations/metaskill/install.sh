#!/usr/bin/env bash
# Storage Analyzer - Metaskill Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main/integrations/metaskill/install.sh | bash

set -e

DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills/storage-analyzer}"
REPO_URL="https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main"

echo "Installing Storage Analyzer for Claude Code / Metaskill..."

mkdir -p "$DEST_DIR"

# Download SKILL.md
if command -v curl &> /dev/null; then
  curl -fsSL "$REPO_URL/integrations/metaskill/SKILL.md" -o "$DEST_DIR/SKILL.md"
  curl -fsSL "$REPO_URL/integrations/metaskill/flows/storage-analyzer.md" -o "$DEST_DIR/flows/storage-analyzer.md"
elif command -v wget &> /dev/null; then
  wget -q "$REPO_URL/integrations/metaskill/SKILL.md" -O "$DEST_DIR/SKILL.md"
  wget -q "$REPO_URL/integrations/metaskill/flows/storage-analyzer.md" -O "$DEST_DIR/flows/storage-analyzer.md"
else
  echo "Error: curl or wget required"
  exit 1
fi

echo ""
echo "Storage Analyzer installed for Claude Code!"
echo "Location: $DEST_DIR"
echo ""
echo "Usage in Claude Code:"
echo "  /storage-analyzer C:\\                  # Analyze C: drive"
echo "  /storage-analyzer --dupes              # Find duplicates"
echo "  /storage-analyzer --report             # Generate HTML report"
echo ""
echo "Or install the full project for more features:"
echo "  pip install storage-analyzer"
