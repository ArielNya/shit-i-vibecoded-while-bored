"""Several Blenders at once: each add-on takes the next free port (9876, 9877, ...);
these tools find them and pick which one the other tools talk to."""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from .. import protocol
from ..bridge import BlenderBridge, BlenderCommandError, BlenderConnectionError
from ._common import Blender

SCAN_PORTS = 10


async def _probe(base: BlenderBridge, port: int) -> dict[str, Any] | None:
    config = dataclasses.replace(base.config, port=port, timeout=3.0)
    bridge = BlenderBridge(config)
    try:
        reply = await bridge.call("ping")
        info = bridge.server_info or {}
        return {
            "port": port,
            "blender_version": info.get("blender_version"),
            "addon_version": info.get("addon_version"),
            "file": reply.get("file"),
            "scene": reply.get("scene"),
            "objects": reply.get("objects"),
        }
    except BlenderCommandError as exc:
        return {"port": port, "error": str(exc)}  # a Blender, but e.g. another token
    except BlenderConnectionError:
        return None  # nothing listening
    finally:
        await bridge.close()


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def list_blender_instances(
        first_port: Annotated[int, Field(ge=1024, le=65535)] = protocol.DEFAULT_PORT,
        count: Annotated[int, Field(ge=1, le=50)] = SCAN_PORTS,
    ) -> dict[str, Any]:
        """Find running Blenders with the add-on (scans ports from first_port). Shows each
        one's open file and scene, and which one the tools currently use."""
        ports = range(first_port, min(first_port + count, 65536))
        found = await asyncio.gather(*(_probe(blender.bridge, p) for p in ports))
        instances = [i for i in found if i is not None]
        for item in instances:
            item["active"] = item["port"] == blender.bridge.config.port
        return {"active_port": blender.bridge.config.port, "instances": instances}

    @mcp.tool()
    async def use_blender(
        port: Annotated[int, Field(ge=1, le=65535, description="From list_blender_instances")],
    ) -> dict[str, Any]:
        """Switch all tools to the Blender listening on this port."""
        found = await _probe(blender.bridge, port)
        if found is None:
            raise ToolError(f"No Blender with the add-on is listening on port {port}.")
        if "error" in found:
            raise ToolError(f"Blender on port {port} refused the connection: {found['error']}")
        await blender.bridge.switch_port(port)
        return {"active_port": port, **found}
