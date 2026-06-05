#!/usr/bin/env bash
# Storage Analyzer - OpenSquilla Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main/integrations/opensquilla/install.sh | bash

set -e

DEST_DIR="${OPENSQUILLA_SKILLS_DIR:-$HOME/.opensquilla/skills/storage-analyzer}"
REPO_URL="https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main"

echo "Installing Storage Analyzer for OpenSquilla..."

mkdir -p "$DEST_DIR/scripts" "$DEST_DIR/references"

# Download SKILL.md
if command -v curl &> /dev/null; then
  curl -fsSL "$REPO_URL/integrations/opensquilla/SKILL.md" -o "$DEST_DIR/SKILL.md"
  curl -fsSL "$REPO_URL/integrations/opensquilla/scripts/analyze.py" -o "$DEST_DIR/scripts/analyze.py"
elif command -v wget &> /dev/null; then
  wget -q "$REPO_URL/integrations/opensquilla/SKILL.md" -O "$DEST_DIR/SKILL.md"
  wget -q "$REPO_URL/integrations/opensquilla/scripts/analyze.py" -O "$DEST_DIR/scripts/analyze.py"
else
  echo "Error: curl or wget required"
  exit 1
fi

chmod +x "$DEST_DIR/scripts/analyze.py"

echo ""
echo "Storage Analyzer installed for OpenSquilla!"
echo "Location: $DEST_DIR"
echo ""
echo "Usage:"
echo "  opensquilla skills list                   # Verify installation"
echo "  opensquilla skills view storage-analyzer   # View skill details"
echo ""
echo "Or ask OpenSquilla: 'Analyze my disk usage' or 'Find large files'"
