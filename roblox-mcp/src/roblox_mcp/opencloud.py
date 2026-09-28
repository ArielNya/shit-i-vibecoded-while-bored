"""Minimal Roblox Open Cloud client (stdlib only). API shapes from creator-docs
reference/cloud/openapi.json and universes-api/v1.json."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# Overridable so tests can point at a fake server.
BASE_ENV = "ROBLOX_MCP_OPEN_CLOUD_URL"


class CloudError(Exception):
    pass


def config(*names: str) -> dict[str, str]:
    """Required settings from the environment, with one clear error for what's missing."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise CloudError(f"set {', '.join(missing)} (an Open Cloud API key and the ids from "
                         "the Creator Dashboard) to use this tool")  # fmt: skip
    return {n: os.environ[n] for n in names}


def request(method: str, path: str, body: bytes | None = None,
            content_type: str = "application/json") -> Any:  # fmt: skip
    base = os.environ.get(BASE_ENV, "https://apis.roblox.com").rstrip("/")
    req = urllib.request.Request(f"{base}/{path.lstrip('/')}", data=body, method=method)
    req.add_header("x-api-key", config("ROBLOX_API_KEY")["ROBLOX_API_KEY"])
    if body is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        hint = {
            401: " (API key invalid or missing a scope)",
            403: " (the key isn't allowed for this experience/place, or lacks a scope)",
            429: " (rate limited: Luau execution allows 5 tasks per minute)",
        }.get(e.code, "")
        raise CloudError(f"Open Cloud {method} {path}: HTTP {e.code}{hint}: {detail}") from None
    except urllib.error.URLError as e:
        raise CloudError(f"can't reach Open Cloud ({e.reason})") from None
    return json.loads(text) if text else None


def save_place_version(universe: str, place: str, rbxl: bytes) -> int:
    """Upload a place file as a Saved (not published) version; returns its number.
    Scope: universe-places:write."""
    reply = request("POST", f"universes/v1/{universe}/places/{place}/versions?versionType=Saved",
                    rbxl, "application/octet-stream")  # fmt: skip
    return int(reply["versionNumber"])


def run_luau(universe: str, place: str, version: int, script: str,
             timeout_s: int = 300) -> dict[str, Any]:  # fmt: skip
    """Run a script against a place version headless; waits for the task to finish and
    returns {"state", "results", "error", "logs"}. Scope:
    universe.place.luau-execution-session:write."""
    task = request(
        "POST",
        f"cloud/v2/universes/{universe}/places/{place}/versions/{version}/"
        "luau-execution-session-tasks",
        json.dumps({"script": script, "timeout": f"{timeout_s}s"}).encode(),
    )
    deadline = time.monotonic() + timeout_s + 60
    while task.get("state") not in ("COMPLETE", "FAILED", "CANCELLED"):
        if time.monotonic() > deadline:
            raise CloudError(f"task {task.get('path')} didn't finish in time")
        time.sleep(2)
        task = request("GET", f"cloud/v2/{task['path']}")
    logs = request("GET", f"cloud/v2/{task['path']}/logs") or {}
    messages = [
        m for entry in logs.get("luauExecutionSessionTaskLogs", []) for m in entry["messages"]
    ]
    return {
        "state": task["state"],
        "results": (task.get("output") or {}).get("results", []),
        "error": task.get("error"),
        "logs": messages,
    }
