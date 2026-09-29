"""Roblox avatar assets: one baked texture, and checks against Roblox's specifications."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from ._common import Blender

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
AccessoryType = Literal[
    "hat", "hair", "face", "neck", "shoulder_neck", "shoulder_collar", "shoulder", "front",
    "back", "waist",
]  # fmt: skip


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def bake_texture(
        ctx: Context,
        object: str,
        path: Annotated[str, Field(description=".png in the workspace")],
        size: Annotated[
            int, Field(ge=16, le=4096, description="Pixels; Marketplace items at most 2048")
        ] = 1024,
        island_margin: Annotated[float, Field(ge=0, le=1)] = 0.02,
        margin: Annotated[int, Field(ge=0, le=64, description="Bleed in pixels")] = 8,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Give a mesh one texture: smart-UV-unwrap it to a new UV map, bake the colour of
        all its materials (flat colours, textures, procedurals) into one image, save the
        PNG, and replace its materials with one material using that image. Roblox meshes
        take one material, one UV set and one colour map (MeshPart.TextureID). Join the
        parts into one mesh first."""
        return await blender.call(
            "bake_texture", progress=ctx, timeout=600, object=object, path=path, size=size,
            island_margin=island_margin, margin=margin, overwrite=overwrite,
        )  # fmt: skip

    @mcp.tool()
    async def check_roblox_asset(
        kind: Annotated[
            Literal["rigid", "layered", "body"],
            Field(
                description="rigid accessory (hat, hair, back...), layered clothing, or a "
                "15-part character body"
            ),
        ] = "rigid",
        object: Annotated[
            str | None, Field(description="The accessory mesh (rigid / layered)")
        ] = None,
        accessory_type: AccessoryType = "hat",
        body_scale: Literal["normal", "slender", "classic"] = "normal",
        attachment: Annotated[
            Vec3 | None,
            Field(
                description="Rigid: world position of the attachment point (e.g. Hat_Att "
                "on Roblox's rig template); size limits are measured from it"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Check a model against Roblox's avatar specifications (1 unit = 1 stud, Z up, the
        front is -Y): triangle budgets, watertight, one material / UV map, texture size,
        size limits around the attachment, and for layered clothing and bodies the cages,
        R15 bones, at most 4 influences and _Att attachments. Returns ok, errors (fix
        before export) and warnings."""
        if kind != "body" and object is None:
            raise ValueError("give the accessory mesh as object")
        return await blender.call(
            "check_roblox_asset", kind=kind, object=object, accessory_type=accessory_type,
            body_scale=body_scale, attachment=attachment,
        )  # fmt: skip
