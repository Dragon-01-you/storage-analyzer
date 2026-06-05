#!/usr/bin/env bash
# Storage Analyzer - Universal Integration Installer
# Installs Storage Analyzer for all supported AI agent platforms
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main/install-integrations.sh | bash
#   --claude     Install for Claude Code only
#   --opensquilla Install for OpenSquilla only
#   --all        Install for all platforms (default)

set -e

REPO_URL="https://raw.githubusercontent.com/Dragon-01-you/storage-analyzer/main"

install_claude() {
  local dest="$HOME/.claude/skills/storage-analyzer"
  echo "[1/2] Installing for Claude Code / Metaskill..."
  mkdir -p "$dest/flows"

  if command -v curl &> /dev/null; then
    curl -fsSL "$REPO_URL/integrations/metaskill/SKILL.md" -o "$dest/SKILL.md"
    curl -fsSL "$REPO_URL/integrations/metaskill/flows/storage-analyzer.md" -o "$dest/flows/storage-analyzer.md"
  else
    wget -q "$REPO_URL/integrations/metaskill/SKILL.md" -O "$dest/SKILL.md"
    wget -q "$REPO_URL/integrations/metaskill/flows/storage-analyzer.md" -O "$dest/flows/storage-analyzer.md"
  fi
  echo "   -> $dest"
}

install_opensquilla() {
  local dest="$HOME/.opensquilla/skills/storage-analyzer"
  echo "[2/2] Installing for OpenSquilla..."
  mkdir -p "$dest/scripts" "$dest/references"

  if command -v curl &> /dev/null; then
    curl -fsSL "$REPO_URL/integrations/opensquilla/SKILL.md" -o "$dest/SKILL.md"
    curl -fsSL "$REPO_URL/integrations/opensquilla/scripts/analyze.py" -o "$dest/scripts/analyze.py"
  else
    wget -q "$REPO_URL/integrations/opensquilla/SKILL.md" -O "$dest/SKILL.md"
    wget -q "$REPO_URL/integrations/opensquilla/scripts/analyze.py" -O "$dest/scripts/analyze.py"
  fi
  chmod +x "$dest/scripts/analyze.py"
  echo "   -> $dest"
}

echo "=== Storage Analyzer - Integration Installer ==="
echo ""

TARGET="${1:---all}"

case "$TARGET" in
  --claude)
    install_claude
    ;;
  --opensquilla)
    install_opensquilla
    ;;
  --all|*)
    install_claude
    install_opensquilla
    ;;
esac

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Claude Code:"
echo "  /storage-analyzer [path]  - Analyze disk"
echo "  /storage-analyzer --dupes - Find duplicates"
echo ""
echo "OpenSquilla:"
echo "  Ask: 'Analyze my disk usage' or 'Find large files'"
echo "  opensquilla skills list   - Verify installation"
echo ""
echo "Full project: https://github.com/Dragon-01-you/storage-analyzer"
