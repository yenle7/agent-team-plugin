# agent-team

A small-startup-team of Claude Code subagents that take a consumer-app feature from **Think → Plan → Build → Review → Test → Ship → Reflect**, logging every phase to Notion so you can see what's happening across products.

This is a Claude Code plugin. Install it once per machine, then use it across N product repos by dropping a tiny `agents.config.json` into each.

## The team

| Phase | Agent | Model | What it does |
|---|---|---|---|
| Think | `/founder-check` | Haiku | 30-second gut check: GO / DEFER / KILL. Stops bad ideas before they cost a plan cycle. |
| Think | `/customer-voice` | Haiku | Pulls real user quotes from feedback sources, feeds them to `/plan` and `/reflect`. |
| Plan | `/plan` | Opus | YC office-hours style. Six forcing questions. Four modes (Expansion / Selective / Hold / Reduction). |
| Plan | `/plan-eng-review` | Sonnet | Eng Manager. Architecture, data flow, hidden assumptions, test strategy. |
| Plan | `/designer` | Sonnet | Landscape scan, two directions, mockups with real content. Anti-slop. |
| Plan | `/plan-design-review` | Sonnet | Senior designer. Rates 0–10 across 7 dimensions, edits design.md to push to a 10. |
| Build | `/build` | Sonnet | Implementer with mandatory pre-flight. Asks for input on ambiguities, atomic commits. |
| Review | `/review` | Sonnet | Staff engineer. Bugs CI won't catch. Auto-fixes obvious; flags judgment calls. |
| Test | `/qa` | Sonnet | Runs the app, exercises scenarios, fixes obvious bugs with regression tests. |
| Test | `/investigate` | Sonnet | Iron Law: no fixes without investigation. Stops after 3 failed attempts. |
| Ship | `/ship` | Haiku | Feature flag, analytics event, PR, release notes. |
| Reflect | `/reflect` | Haiku | 7-day retro from real usage data. Lessons append to team memory. |

## Install (once per machine)

```bash
# 1. Push this plugin repo to GitHub (private is fine).
cd /Users/yen/Documents/Birdie/agent_team_plugin
git init && git add . && git commit -m "initial scaffold"
gh repo create agent-team-plugin --private --source=. --push   # or your remote of choice

# 2. Install the plugin into Claude Code (the repo itself acts as the marketplace).
claude plugin marketplace add https://github.com/<you>/agent-team-plugin.git
claude plugin install agent-team@agent-team-plugin

# 3. Verify.
claude plugin list
# Open any folder, run `claude`, then `/agents` — you should see all 12 agents.
```

## Bootstrap a product repo (once per product)

```bash
cd ~/Documents/Birdie/birdie_care    # or birdie-play, or any future product
bash ~/.claude/plugins/agent-team/scripts/install.sh
```

What that does, idempotently:
- Creates `.claude/agents.config.json` from the template, prefilled with `product_tag` from the folder name.
- Creates or merges `.claude/settings.json` to register the Task-tool PreToolUse/PostToolUse hooks.
- Registers the Notion MCP for this repo (`claude mcp add notion …`).
- Adds `.claude/state/` to `.gitignore`.

Then **fill in two things by hand**:
1. Open `.claude/agents.config.json` and replace `REPLACE_WITH_NOTION_DATABASE_ID` with your actual Notion database id.
2. Export `NOTION_TOKEN` in your shell (and add it to your dotfiles or 1Password CLI).

## The Notion database schema

Create one database (or use the existing one, with a `Product` property to multiplex products). Required properties:

| Property | Type | Notes |
|---|---|---|
| Name | Title | Auto-filled from the ticket |
| Phase | Select | Think / Plan / Build / Review / Test / Ship / Reflect / Other |
| Agent | Select | `plan`, `build`, etc. |
| Status | Select | Not started / Triggered / Triggered (running) / In progress / Done / Blocked |
| Product | Select | Birdie / Birdie Play / … |
| Started | Date | |
| Finished | Date | |
| Artifact link | URL | Optional — link to the `tickets/<id>/<phase>.md` file in GitHub |
| Parent ticket | Relation (self) | Lets you group child tickets under a feature |

## Daily usage

Open a terminal in your product repo. **One Claude Code session handles the whole flow** — you don't open a tab per agent.

```bash
cd ~/Documents/Birdie/birdie_care
claude
```

A typical feature day:

```
> /founder-check "add password reset"        # 30 sec gate
> /plan "add password reset"                  # writes tickets/<id>/plan.md
> /plan-eng-review                            # writes eng-review.md
> /designer                                   # writes design.md (can parallel with eng-review)
> /plan-design-review                         # edits design.md, writes design-review.md
> /build <id>                                 # pre-flight, asks for input, then commits
> /review                                     # auto-fix + flag
> /qa                                         # run app, find bugs
> /investigate <bug-id>                       # if /qa hands off a deep bug
> /ship <id>                                  # flag, analytics, PR, release notes
# ... 7 days later ...
> /reflect <id>                               # retro from real usage data
```

Each agent reads its predecessor's artifact file — not your conversation history. That's the token-efficiency trick: you can close the terminal and come back, and the next agent picks up from disk.

## Three trigger modes

1. **Manual.** Just type `/plan ...` etc. in your session. (Most common.)
2. **Ticket-driven.** Create a Notion row with `Agent: build`, `Status: Triggered`. The poller (cron, every 5 min) sees it and runs `claude -p "/build <description>"` in headless mode.
3. **Scheduled.** `scripts/standup.sh` invokes `/standup` from cron every morning at 6am. Add your own cron entries for `/reflect`-on-flag-7d, weekly audits, etc.

## Iterate on the team

While testing, edit the *installed* copy (faster than round-tripping through git):

```bash
$EDITOR ~/.claude/plugins/agent-team/agents/build.md
# in your live claude session:
> /agents reload    # (or restart claude)
> /build <id>       # test the new prompt
```

When a change feels right, promote it back into the plugin repo:

```bash
bash ~/.claude/plugins/agent-team/scripts/promote-agent.sh build
cd ~/Documents/Birdie/agent_team_plugin
git diff agents/build.md
git commit -am "build: stricter pre-flight on ambiguous specs"
git push
# On other machines:
claude plugin update agent-team
```

## Multi-product setup

You have two products today (`birdie_care`, `birdie-play`). Each gets its own bootstrap:

```bash
cd ~/Documents/Birdie/birdie_care    && bash ~/.claude/plugins/agent-team/scripts/install.sh
cd ~/Documents/Birdie/birdie-play    && bash ~/.claude/plugins/agent-team/scripts/install.sh
```

Same plugin, different configs. The Notion `Product` property lets you filter tickets per product in one shared database. Adding a third product is one `install.sh` call away.

## What's where

```
agent_team_plugin/
├── .claude-plugin/
│   └── plugin.json              ← plugin manifest (Claude Code reads it from here)
├── README.md                    ← short overview
├── README.agents.md             ← this file
├── agents/                      ← 12 .md subagent files
├── hooks/
│   ├── notion_ticket.py         ← writes phase-tagged tickets on SubagentStart/Stop
│   └── settings.snippet.json    ← what install.sh merges into product .claude/settings.json
├── scripts/
│   ├── install.sh               ← bootstrap a new product repo
│   ├── standup.sh               ← cron entry for daily digest
│   ├── poller.sh                ← cron entry for ticket-driven trigger
│   ├── _poller.py               ← helper for poller.sh
│   └── promote-agent.sh         ← copy locally-edited agent back into plugin repo
└── templates/
    └── agents.config.json       ← per-product config template
```

## Things to verify before relying on this

- **`plugin.json` schema.** The Claude Code plugin manifest format is evolving. Confirm field names against [the current docs](https://code.claude.com/docs/en/plugins) before publishing.
- **Subagent directory name.** Recent Claude Code versions use `agents/` inside the plugin; some older docs reference `subagents/`. Run `claude /agents` from a repo that has the plugin installed — if your agents don't show up, try renaming the folder.
- **Hook event names.** The hook fires on `PreToolUse` / `PostToolUse` with matcher `Task` — there is no `SubagentStart` event. The subagent name is read from `tool_input.subagent_type`.
- **Notion property names.** The hook uses `Name`, `Phase`, `Agent`, `Status`, `Product`, `Started`, `Finished`. Override in `agents.config.json` if your DB uses different names.

## Cost note

Rough monthly token cost for a 1-feature-per-day cadence with the model tiering above is meaningfully lower than running everything on Sonnet (let alone Opus). The two biggest savers:
1. **Artifact handoffs** — each agent reads ~1 file, not the whole conversation.
2. **Model tiering** — Haiku on `/founder-check`, `/ship`, `/reflect`, `/standup`; Opus only on `/plan`.

If you want even cheaper, dial `/plan` down to Sonnet — it's the single biggest line item.
