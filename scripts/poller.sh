#!/usr/bin/env bash
# poller.sh — watch Notion for tickets flipped to Status="Triggered" and
# kick off the matching agent in headless Claude Code.
#
# Run from cron every few minutes:
#   */5 * * * * cd ~/code/birdie_care && bash ~/.claude/plugins/agent-team/scripts/poller.sh
#
# The poller reads agents.config.json for the Notion DB id, queries for
# tickets where Status = Triggered AND Product = <product_tag>, then for
# each row:
#   1. Reads the Agent property (e.g. "plan", "build")
#   2. Reads the Task description (Name + a "Description" rich-text property)
#   3. Flips Status to "Triggered (running)" so it doesn't re-fire
#   4. Invokes `claude -p "/<agent> <description>"` in headless mode
#   5. On completion, the hook script handles the Notion update normally

set -euo pipefail

REPO_DIR="$(pwd)"
CFG="${REPO_DIR}/.claude/agents.config.json"

if [ ! -f "${CFG}" ]; then
  echo "poller.sh: no agents.config.json in ${REPO_DIR} — skipping." >&2
  exit 0
fi
if [ -z "${NOTION_TOKEN:-}" ]; then
  echo "poller.sh: NOTION_TOKEN not set — skipping." >&2
  exit 0
fi

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${PLUGIN_DIR}/scripts/_poller.py" "${REPO_DIR}"
