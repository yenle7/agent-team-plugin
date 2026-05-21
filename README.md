# agent-team

A Claude Code plugin: a small-startup-team of 12 subagents that take a consumer-app
feature from **Think → Plan → Build → Review → Test → Ship → Reflect**, logging every
phase to Notion.

See [README.agents.md](README.agents.md) for the full guide — the team roster, the
Notion schema, per-product bootstrap, and daily usage.

## Quick start

```bash
# Install the plugin (once per machine)
claude plugin marketplace add https://github.com/yenle7/agent-team-plugin.git
claude plugin install agent-team@agent-team-plugin

# Bootstrap a product repo (once per product)
cd ~/path/to/your-product
bash ~/.claude/plugins/agent-team/scripts/install.sh
```
