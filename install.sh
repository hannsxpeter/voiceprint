#!/usr/bin/env sh
# Install the voiceprint skill into supported coding-agent skill directories.
#
# Usage:
#   ./install.sh <all|claude|codex|cursor|windsurf>
#
# Override destinations with:
#   CLAUDE_SKILLS_DIR=/path/to/skills ./install.sh claude
#   CODEX_SKILLS_DIR=/path/to/skills ./install.sh codex
#   CURSOR_SKILLS_DIR=/path/to/skills ./install.sh cursor
#   WINDSURF_SKILLS_DIR=/path/to/skills ./install.sh windsurf

set -eu

unset CDPATH
SRC_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
VERSION=$(awk '/^  version: / { print $2; exit }' "$SRC_DIR/SKILL.md")
TARGET="${1:-}"

install_skill() {
  label=$1
  dest=$2
  skill_dest="$dest/voiceprint"

  mkdir -p "$skill_dest/scripts" "$skill_dest/vendor" "$skill_dest/.cursor/rules" "$skill_dest/.github"

  cp "$SRC_DIR/SKILL.md" "$skill_dest/SKILL.md"
  cp "$SRC_DIR/AGENTS.md" "$skill_dest/AGENTS.md"
  cp "$SRC_DIR/GEMINI.md" "$skill_dest/GEMINI.md"
  cp "$SRC_DIR/LICENSE" "$skill_dest/LICENSE"
  cp "$SRC_DIR/README.md" "$skill_dest/README.md"
  cp "$SRC_DIR/scripts/text_hygiene.py" "$skill_dest/scripts/text_hygiene.py"
  chmod +x "$skill_dest/scripts/text_hygiene.py" 2>/dev/null || true

  rm -rf "$skill_dest/vendor"
  cp -R "$SRC_DIR/vendor" "$skill_dest/vendor"

  if [ -d "$SRC_DIR/docs" ]; then
    rm -rf "$skill_dest/docs"
    cp -R "$SRC_DIR/docs" "$skill_dest/docs"
  fi
  if [ -d "$SRC_DIR/assets" ]; then
    rm -rf "$skill_dest/assets"
    cp -R "$SRC_DIR/assets" "$skill_dest/assets"
  fi

  mkdir -p "$skill_dest/.cursor/rules"
  cp "$SRC_DIR/.cursor/rules/voiceprint.mdc" "$skill_dest/.cursor/rules/voiceprint.mdc"
  mkdir -p "$skill_dest/.github"
  cp "$SRC_DIR/.github/copilot-instructions.md" "$skill_dest/.github/copilot-instructions.md"

  echo "Installed voiceprint v$VERSION for $label to $skill_dest"
}

install_claude() {
  install_skill "Claude Code" "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
}

install_codex() {
  install_skill "Codex" "${CODEX_SKILLS_DIR:-${CODEX_HOME:-$HOME/.codex}/skills}"
}

install_cursor() {
  install_skill "Cursor" "${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}"
}

install_windsurf() {
  install_skill "Windsurf/Cascade" "${WINDSURF_SKILLS_DIR:-$HOME/.codeium/windsurf/skills}"
}

usage() {
  echo "Usage: ./install.sh <all|claude|codex|cursor|windsurf>" >&2
  echo "" >&2
  echo "Targets:" >&2
  echo "  all       Install for Claude Code, Codex, Cursor, and Windsurf/Cascade" >&2
  echo "  claude    Install for Claude Code" >&2
  echo "  codex     Install for Codex" >&2
  echo "  cursor    Install for Cursor" >&2
  echo "  windsurf  Install for Windsurf/Cascade" >&2
}

case "$TARGET" in
  "")
    usage
    exit 0
    ;;
  all)
    install_claude
    install_codex
    install_cursor
    install_windsurf
    ;;
  claude)
    install_claude
    ;;
  codex)
    install_codex
    ;;
  cursor)
    install_cursor
    ;;
  windsurf | cascade)
    install_windsurf
    ;;
  *)
    usage
    exit 2
    ;;
esac

echo "Restart the target coding agent to pick it up."
