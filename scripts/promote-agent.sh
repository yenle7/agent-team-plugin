#!/usr/bin/env bash
# promote-agent.sh — copy a locally-edited agent from the INSTALLED plugin
# location back into the PLUGIN REPO so the change can be committed and
# pushed to every machine.
#
# Usage:  bash ~/.claude/plugins/agent-team/scripts/promote-agent.sh <agent-name>
#
# Example workflow:
#   1. You edit ~/.claude/plugins/agent-team/agents/build.md while testing.
#   2. The new prompt feels right.
#   3. Run: bash ~/.claude/plugins/agent-team/scripts/promote-agent.sh build
#   4. cd into your plugin repo (path printed by this script), git diff,
#      commit, push. Then `claude plugin update agent-team` on other machines.

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <agent-name>"
  echo "Example: $0 build"
  exit 1
fi

AGENT="$1"
INSTALLED="${HOME}/.claude/plugins/agent-team/agents/${AGENT}.md"

# The plugin repo is wherever the user keeps it. Prefer an env var; else guess.
PLUGIN_REPO="${AGENT_TEAM_PLUGIN_REPO:-${HOME}/Documents/Birdie/agent_team_plugin}"

if [ ! -f "${INSTALLED}" ]; then
  echo "  No installed agent at ${INSTALLED}"
  exit 1
fi
if [ ! -d "${PLUGIN_REPO}" ]; then
  echo "  Plugin repo not found at ${PLUGIN_REPO}"
  echo "    Set AGENT_TEAM_PLUGIN_REPO env var to override."
  exit 1
fi

DEST="${PLUGIN_REPO}/agents/${AGENT}.md"

cp "${INSTALLED}" "${DEST}"
echo "    Copied ${AGENT}.md into plugin repo: ${DEST}"
echo ""
echo "Next:"
echo "    cd ${PLUGIN_REPO}"
echo "    git diff agents/${AGENT}.md"
echo "    git add agents/${AGENT}.md && git commit -m \"${AGENT}: <describe change>\""
echo "    git push"
echo ""
echo "    Then on each machine:  claude plugin update agent-team"
