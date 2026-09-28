from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from ..bridge import BlenderBridge, BlenderCommandError, BlenderConnectionError

PROGRESS_INTERVAL = 2.0


class Blender:
    """What tool modules use to reach Blender: bridge calls with MCP-friendly errors."""

    def __init__(self, bridge: BlenderBridge):
        self.bridge = bridge

    async def call(
        self,
        method: str,
        timeout: float | None = None,
        progress: Context | None = None,
        **params: Any,
    ) -> Any:
        """Call a handler in Blender. With `progress` (the tool's Context), send an
        elapsed-time progress notification every few seconds while Blender works, so
        clients show activity and don't give up on long renders or edits."""
        params = {key: value for key, value in params.items() if value is not None}
        heartbeat = None
        if progress is not None:
            heartbeat = asyncio.create_task(_heartbeat(progress, method))
        try:
            return await self.bridge.call(method, params, timeout=timeout)
        except BlenderConnectionError as exc:
            raise ToolError(str(exc)) from exc
        except BlenderCommandError as exc:
            detail = f"\n{exc.data}" if exc.data else ""
            raise ToolError(f"Blender error: {exc}{detail}") from exc
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await heartbeat


async def _heartbeat(ctx: Context, method: str) -> None:
    started = time.monotonic()
    while True:
        await asyncio.sleep(PROGRESS_INTERVAL)
        elapsed = time.monotonic() - started
        try:
            await ctx.report_progress(
                round(elapsed, 1), None, f"Blender is working on {method} ({elapsed:.0f}s)"
            )
        except Exception:
            return  # progress is best-effort; never break the actual call
