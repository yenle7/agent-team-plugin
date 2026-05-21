#!/usr/bin/env python3
"""
_poller.py — internal helper for poller.sh.

Queries the Notion DB for tickets where Status = "Triggered" and Product =
<product_tag>, and for each ticket invokes the matching agent in headless
Claude Code. Marks the ticket as "Triggered (running)" before kicking off
so it doesn't fire twice.

This is intentionally minimal — no retries, no parallelism, no fancy queue.
A startup-scale tool. Swap for something more robust if you outgrow it.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def notion(method, path, body, token):
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
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    repo_root = Path(sys.argv[1])
    cfg = json.loads((repo_root / ".claude" / "agents.config.json").read_text())
    token = os.environ["NOTION_TOKEN"]
    db_id = cfg["notion"]["database_id"]
    product = cfg.get("product_tag", "?")

    query = {
        "filter": {
            "and": [
                {"property": cfg["notion"].get("status_property", "Status"),
                 "select": {"equals": "Triggered"}},
                {"property": cfg["notion"].get("product_property", "Product"),
                 "select": {"equals": product}},
            ]
        }
    }
    res = notion("POST", f"/databases/{db_id}/query", query, token)

    for page in res.get("results", []):
        props = page["properties"]
        agent = props.get(cfg["notion"].get("agent_property", "Agent"), {}).get("select", {}).get("name")
        title_parts = props.get("Name", {}).get("title", [])
        title = "".join(p.get("plain_text", "") for p in title_parts) or "(no title)"

        if not agent:
            print(f"  {page['id']}: no Agent set — skipping")
            continue

        # Lock the row so we don't re-fire
        notion("PATCH", f"/pages/{page['id']}",
               {"properties": {cfg["notion"].get("status_property", "Status"):
                               {"select": {"name": "Triggered (running)"}}}},
               token)

        prompt = f"/{agent} {title}"
        print(f">>> firing: {prompt}")
        subprocess.Popen(
            ["claude", "-p", prompt],
            cwd=str(repo_root),
            stdout=open(repo_root / ".claude" / "state" / "poller.log", "a"),
            stderr=subprocess.STDOUT,
        )


if __name__ == "__main__":
    main()
