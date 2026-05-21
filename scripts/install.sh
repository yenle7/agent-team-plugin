#!/usr/bin/env bash
# install.sh — bootstrap the agent-team plugin into a product repo.
#
# Usage:  cd <product-repo> && bash ~/.claude/plugins/agent-team/scripts/install.sh
#
# Creates .claude/agents.config.json and merges the hook config into
# .claude/settings.json. Idempotent — safe to re-run.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(pwd)"

if [ ! -d "${REPO_DIR}/.git" ] && [ ! -f "${REPO_DIR}/package.json" ] && [ ! -f "${REPO_DIR}/pyproject.toml" ]; then
  echo "  Doesn't look like a product repo (no .git, package.json, or pyproject.toml here)."
  echo "    cd into your product repo first, then re-run."
  exit 1
fi

echo ">>> agent-team install: bootstrapping ${REPO_DIR}"

mkdir -p "${REPO_DIR}/.claude"
mkdir -p "${REPO_DIR}/tickets"

# --- 1. agents.config.json ---
CFG="${REPO_DIR}/.claude/agents.config.json"
if [ -f "${CFG}" ]; then
  echo "    .claude/agents.config.json already exists — leaving it alone."
else
  cp "${PLUGIN_DIR}/templates/agents.config.json" "${CFG}"
  echo "    Created .claude/agents.config.json from template."

  # Try to prefill product_tag from the repo folder name.
  TAG=$(basename "${REPO_DIR}")
  # macOS-safe sed -i
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|\"product_tag\": \"Birdie\"|\"product_tag\": \"${TAG}\"|" "${CFG}"
  else
    sed -i "s|\"product_tag\": \"Birdie\"|\"product_tag\": \"${TAG}\"|" "${CFG}"
  fi
  echo "       Set product_tag = ${TAG}. Edit the file to fill in the Notion DB id and tune the rest."
fi

# --- 2. settings.json merge (hooks) ---
SETTINGS="${REPO_DIR}/.claude/settings.json"
SNIPPET="${PLUGIN_DIR}/hooks/settings.snippet.json"

if [ ! -f "${SETTINGS}" ]; then
  # No settings file yet — copy the snippet (minus the _comment key) as the starting point.
  python3 -c "
import json, sys
snippet = json.load(open('${SNIPPET}'))
snippet.pop('_comment', None)
json.dump(snippet, open('${SETTINGS}', 'w'), indent=2)
"
  echo "    Created .claude/settings.json with hook configuration."
else
  # Merge hooks into existing settings file.
  python3 -c "
import json
existing = json.load(open('${SETTINGS}'))
snippet  = json.load(open('${SNIPPET}'))
snippet.pop('_comment', None)
existing.setdefault('hooks', {})
for event, handlers in snippet.get('hooks', {}).items():
    existing['hooks'].setdefault(event, [])
    for h in handlers:
        if h not in existing['hooks'][event]:
            existing['hooks'][event].append(h)
json.dump(existing, open('${SETTINGS}', 'w'), indent=2)
"
  echo "    Merged hook handlers into existing .claude/settings.json."
fi

# --- 3. Notion MCP registration (idempotent best-effort) ---
if command -v claude >/dev/null 2>&1; then
  if claude mcp list 2>/dev/null | grep -q "notion"; then
    echo "    Notion MCP already registered in this repo."
  else
    echo ">>> Registering Notion MCP for this repo..."
    claude mcp add --transport http notion https://mcp.notion.com/mcp \
      && echo "    Notion MCP registered." \
      || echo "      Failed to register Notion MCP — run manually: claude mcp add --transport http notion https://mcp.notion.com/mcp"
  fi
else
  echo "      'claude' CLI not on PATH; skipping Notion MCP registration."
fi

# --- 4. Gitignore noisy state ---
GI="${REPO_DIR}/.gitignore"
touch "${GI}"
for line in ".claude/state/" "tickets/_team-memory.md" ".env.local"; do
  if ! grep -qxF "${line}" "${GI}"; then
    echo "${line}" >> "${GI}"
  fi
done
echo "    Updated .gitignore."

echo ""
echo "Done. Next steps:"
echo "  1. Open .claude/agents.config.json and fill in your Notion database_id."
echo "  2. Export NOTION_TOKEN in your shell (and add to your dotfiles)."
echo "  3. Run 'claude' in this repo, then try:  /founder-check \"add password reset\""
echo ""
