#!/usr/bin/env python3
"""
notion_ticket.py — Claude Code hook that writes phase-tagged tickets to Notion
when a subagent starts or stops.

How it's wired:
  - Registered by the plugin itself via hooks/hooks.json — no per-repo
    settings.json edit needed. It fires on the Task tool: PreToolUse
    ("start") and PostToolUse ("finish"), matcher "Task".
  - Claude Code pipes a JSON payload on stdin (session_id, tool_input, etc.).
    For Task-tool events the subagent name is in tool_input.subagent_type.
  - Fails soft in any repo that has no .claude/agents.config.json, so it is
    harmless to leave active globally.
  - This script reads .claude/agents.config.json from the *consuming repo's cwd*
    to know which Notion DB to write to and which product tag to stamp.
  - State (the Notion page_id created on start) is cached in
    .claude/state/<session_id>-<subagent>.json so the finish call can find it.

Required env:
  - NOTION_TOKEN     — set in the user's shell, or read from a per-repo .env
  - (optional) NOTION_API_VERSION (default 2022-06-28)

This script intentionally fails soft: if anything goes wrong, it logs to
.claude/state/hook-errors.log and exits 0 so it never blocks Claude Code.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = os.environ.get("NOTION_API_VERSION", "2022-06-28")

# Map subagent name -> phase label that goes into the Notion ticket
PHASE_MAP = {
    "founder-check":      "Think",
    "customer-voice":     "Think",
    "plan":               "Plan",
    "plan-eng-review":    "Plan",
    "designer":           "Plan",
    "plan-design-review": "Plan",
    "build":              "Build",
    "review":             "Review",
    "qa":                 "Test",
    "investigate":        "Test",
    "ship":               "Ship",
    "reflect":            "Reflect",
}


def log_error(repo_root: Path, msg: str) -> None:
    state_dir = repo_root / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "hook-errors.log").open("a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}  {msg}\n")


def load_config(repo_root: Path) -> dict | None:
    cfg_path = repo_root / ".claude" / "agents.config.json"
    if not cfg_path.exists():
        return None
    try:
        return json.loads(cfg_path.read_text())
    except Exception as e:
        log_error(repo_root, f"failed to parse agents.config.json: {e}")
        return None


def notion_request(method: str, path: str, body: dict | None, token: str) -> dict:
    req = urllib.request.Request(
        url=f"{NOTION_API}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body else None,
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_subagent(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    return (
        tool_input.get("subagent_type")
        or payload.get("subagent_type")
        or payload.get("subagent")
        or "unknown"
    )


def rich_text(s: str) -> dict:
    """Build a Notion rich_text property value, truncated to Notion's 2000-char cap."""
    s = (s or "").strip()
    if len(s) > 2000:
        s = s[:1997] + "..."
    return {"rich_text": [{"text": {"content": s}}] if s else []}


def get_task_description(payload: dict) -> str:
    """The task text handed to the subagent (Task tool's prompt)."""
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("prompt") or tool_input.get("description") or ""


def get_result_summary(payload: dict) -> str:
    """What the subagent reported back (Task tool's response)."""
    resp = payload.get("tool_response")
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, list):
        parts = []
        for item in resp:
            if isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(resp, dict):
        return resp.get("text") or resp.get("content") or json.dumps(resp)
    return str(resp)


def state_file(repo_root: Path, session_id: str, subagent: str) -> Path:
    state_dir = repo_root / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{session_id}-{subagent}.json"


def handle_start(payload: dict, repo_root: Path, cfg: dict, token: str) -> None:
    subagent = get_subagent(payload)
    session_id = payload.get("session_id", "no-session")
    phase = PHASE_MAP.get(subagent, "Other")
    now_iso = datetime.now(timezone.utc).isoformat()

    db_id = cfg["notion"]["database_id"]
    if db_id == "REPLACE_WITH_NOTION_DATABASE_ID":
        log_error(repo_root, "agents.config.json still has placeholder Notion DB id")
        return

    title = f"{cfg.get('product_tag','?')} — {subagent} @ {now_iso[:16]}"

    props = {
        "Name": {"title": [{"text": {"content": title}}]},
        cfg["notion"].get("phase_property", "Phase"):    {"select": {"name": phase}},
        cfg["notion"].get("agent_property", "Agent"):    {"select": {"name": subagent}},
        cfg["notion"].get("status_property", "Status"):  {"select": {"name": "In progress"}},
        cfg["notion"].get("product_property", "Product"):{"select": {"name": cfg.get("product_tag", "?")}},
        cfg["notion"].get("task_property", "Task"):      rich_text(get_task_description(payload)),
        "Started": {"date": {"start": now_iso}},
    }

    page = notion_request(
        "POST", "/pages",
        {"parent": {"database_id": db_id}, "properties": props},
        token,
    )

    state = {
        "page_id":      page["id"],
        "subagent":     subagent,
        "session_id":   session_id,
        "started_at":   now_iso,
        "phase":        phase,
    }
    state_file(repo_root, session_id, subagent).write_text(json.dumps(state))


def handle_finish(payload: dict, repo_root: Path, cfg: dict, token: str) -> None:
    subagent = get_subagent(payload)
    session_id = payload.get("session_id", "no-session")
    sf = state_file(repo_root, session_id, subagent)
    if not sf.exists():
        log_error(repo_root, f"no state file for {session_id}/{subagent} on finish")
        return

    state = json.loads(sf.read_text())
    now_iso = datetime.now(timezone.utc).isoformat()

    props = {
        cfg["notion"].get("status_property", "Status"): {"select": {"name": "Done"}},
        cfg["notion"].get("summary_property", "Summary"): rich_text(get_result_summary(payload)),
        "Finished": {"date": {"start": now_iso}},
    }
    notion_request("PATCH", f"/pages/{state['page_id']}", {"properties": props}, token)
    sf.unlink()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"

    # Read JSON payload from stdin (Claude Code hook contract)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    # cwd is the consuming repo's root (Claude Code runs hooks from there)
    repo_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    cfg = load_config(repo_root)
    if not cfg:
        return 0  # fail soft — no config, do nothing

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        log_error(repo_root, "NOTION_TOKEN not set; skipping ticket write")
        return 0

    try:
        if mode == "start":
            handle_start(payload, repo_root, cfg, token)
        elif mode == "finish":
            handle_finish(payload, repo_root, cfg, token)
        else:
            log_error(repo_root, f"unknown mode: {mode}")
    except urllib.error.HTTPError as e:
        log_error(repo_root, f"Notion HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        log_error(repo_root, f"{type(e).__name__}: {e}")

    return 0  # always exit 0 — never block Claude Code


if __name__ == "__main__":
    sys.exit(main())
