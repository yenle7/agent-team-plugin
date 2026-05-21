#!/usr/bin/env bash
# standup.sh — daily morning digest, run by cron.
#
# Recommended crontab entry (one per product repo):
#   0 6 * * * cd ~/code/birdie_care && bash ~/.claude/plugins/agent-team/scripts/standup.sh
#
# Invokes /standup in headless mode in the current repo. The /standup agent
# is expected to read yesterday's Notion activity for the configured product
# tag and write a one-page digest to the product's standup page in Notion.
#
# This script intentionally uses --bare to skip MCP/skill auto-discovery
# (the agent itself loads the Notion MCP via its tools allowlist), which
# keeps the cron run cheap.

set -euo pipefail

REPO_DIR="$(pwd)"

if [ ! -f "${REPO_DIR}/.claude/agents.config.json" ]; then
  echo "standup.sh: no agents.config.json in ${REPO_DIR} — skipping." >&2
  exit 0
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "standup.sh: 'claude' CLI not on PATH." >&2
  exit 1
fi

# Headless invocation. --bare keeps the run lean; the /standup agent has its
# own tool allowlist for Notion in its frontmatter.
claude -p "/standup" \
  --allowedTools "Read,Bash,mcp__notion__search_threads,mcp__notion__notion-search,mcp__notion__notion-fetch,mcp__notion__notion-update-page" \
  --bare \
  >> "${REPO_DIR}/.claude/state/standup.log" 2>&1
