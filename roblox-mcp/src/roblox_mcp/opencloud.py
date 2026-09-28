"""Minimal Roblox Open Cloud client (stdlib only). API shapes from creator-docs
reference/cloud/openapi.json and universes-api/v1.json."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

# Overridable so tests can point at a fake server.
BASE_ENV = "ROBLOX_MCP_OPEN_CLOUD_URL"


class CloudError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


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
        message = f"Open Cloud {method} {path}: HTTP {e.code}{hint}: {detail}"
        raise CloudError(message, e.code) from None
    except urllib.error.URLError as e:
        raise CloudError(f"can't reach Open Cloud ({e.reason})") from None
    return json.loads(text) if text else None


def save_place_version(universe: str, place: str, data: bytes, version_type: str = "Saved",
                       xml: bool = False) -> int:  # fmt: skip
    """Upload a place file as a Saved or Published version; returns its number.
    Scope: universe-places:write."""
    path = f"universes/v1/{universe}/places/{place}/versions?versionType={version_type}"
    content_type = "application/xml" if xml else "application/octet-stream"
    return int(request("POST", path, data, content_type)["versionNumber"])


def run_luau(universe: str, place: str, version: int | None, script: str,
             timeout_s: int = 300) -> dict[str, Any]:  # fmt: skip
    """Run a script headless against a place version (None: the latest); waits for the
    task and returns {"state", "results", "error", "logs"}. Scopes:
    universe.place.luau-execution-session:write and :read."""
    at = f"versions/{version}/" if version is not None else ""
    task = request(
        "POST",
        f"cloud/v2/universes/{universe}/places/{place}/{at}luau-execution-session-tasks",
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


def multipart(fields: dict[str, str], file_field: str, filename: str, file_type: str,
              data: bytes) -> tuple[bytes, str]:  # fmt: skip
    """multipart/form-data body and its content type (stdlib has no encoder)."""
    boundary = f"----roblox-mcp-{uuid.uuid4().hex}"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
        .encode() for name, value in fields.items()
    ]  # fmt: skip
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\nContent-Type: {file_type}\r\n\r\n'.encode()
        + data
        + b"\r\n"
    )
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def create_asset(asset: dict[str, Any], filename: str, file_type: str, data: bytes,
                 wait_s: int = 60) -> dict[str, Any]:  # fmt: skip
    """Create an asset and wait for its operation; returns the Asset. Scopes: asset:read,
    asset:write."""
    body, content_type = multipart({"request": json.dumps(asset)}, "fileContent", filename,
                                   file_type, data)  # fmt: skip
    operation = request("POST", "assets/v1/assets", body, content_type)
    deadline = time.monotonic() + wait_s
    while not operation.get("done"):
        if time.monotonic() > deadline:
            raise CloudError(f"upload still processing after {wait_s} s ({operation.get('path')})")
        time.sleep(2)
        operation = request("GET", f"assets/v1/{operation['path']}")
    if operation.get("error"):
        raise CloudError(f"upload failed: {operation['error']}")
    return operation["response"]


def moderation_state(asset_id: int) -> str | None:
    """`Approved`, `Reviewing` or `Rejected`."""
    asset = request("GET", f"assets/v1/assets/{asset_id}?readMask=moderationResult")
    return (asset.get("moderationResult") or {}).get("moderationState")
