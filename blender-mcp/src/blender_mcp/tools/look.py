"""Materials, world lighting, cameras and lights."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Blender
from .mesh import Select

Color = Annotated[
    list[float], Field(min_length=3, max_length=4, description="RGB or RGBA, each 0-1")
]
Unit = Annotated[float, Field(ge=0, le=1)]


def register(mcp: MCPServer, blender: Blender) -> None:
    async def material_call(method: str, **params: Any) -> Any:
        return await blender.call(method, timeout=60, **params)

    material_params = """
        base_color: RGB(A) 0-1. metallic, roughness, alpha, transmission: 0-1.
        emission_color + emission_strength for glowing parts. base_color_texture: an
        image path (inside the workspace), or generated_texture CHECKER / COLOR_GRID
        for a quick test pattern; texture_scale tiles it. The viewport display color
        is kept in sync so Workbench previews match."""

    @mcp.tool(description="Create a Principled BSDF material." + material_params)
    async def create_material(
        name: str,
        base_color: Color | None = None,
        metallic: Unit | None = None,
        roughness: Unit | None = None,
        alpha: Unit | None = None,
        transmission: Unit | None = None,
        ior: Annotated[float | None, Field(ge=1, le=4)] = None,
        emission_color: Color | None = None,
        emission_strength: Annotated[float | None, Field(ge=0)] = None,
        base_color_texture: str | None = None,
        generated_texture: Annotated[
            str | None, Field(description="CHECKER, COLOR_GRID or BLANK")
        ] = None,
        texture_scale: Annotated[float | None, Field(gt=0)] = None,
        replace: Annotated[
            bool, Field(description="Allow creating even if the name exists (gets .001)")
        ] = False,
    ) -> dict[str, Any]:
        return await material_call(
            "create_material", name=name, base_color=base_color, metallic=metallic,
            roughness=roughness, alpha=alpha, transmission=transmission, ior=ior,
            emission_color=emission_color, emission_strength=emission_strength,
            base_color_texture=base_color_texture, generated_texture=generated_texture,
            texture_scale=texture_scale, replace=replace,
        )  # fmt: skip

    @mcp.tool(
        description="Change an existing material. Only given values change." + material_params
    )
    async def update_material(
        name: str,
        base_color: Color | None = None,
        metallic: Unit | None = None,
        roughness: Unit | None = None,
        alpha: Unit | None = None,
        transmission: Unit | None = None,
        ior: Annotated[float | None, Field(ge=1, le=4)] = None,
        emission_color: Color | None = None,
        emission_strength: Annotated[float | None, Field(ge=0)] = None,
        base_color_texture: str | None = None,
        generated_texture: str | None = None,
        texture_scale: Annotated[float | None, Field(gt=0)] = None,
    ) -> dict[str, Any]:
        return await material_call(
            "update_material", name=name, base_color=base_color, metallic=metallic,
            roughness=roughness, alpha=alpha, transmission=transmission, ior=ior,
            emission_color=emission_color, emission_strength=emission_strength,
            base_color_texture=base_color_texture, generated_texture=generated_texture,
            texture_scale=texture_scale,
        )  # fmt: skip

    @mcp.tool()
    async def assign_material(
        object: str,
        material: str,
        faces: Annotated[
            list[int] | None,
            Field(
                description="Face indices to assign to; omit (with select) to make it the "
                "object's only material"
            ),
        ] = None,
        select: Annotated[
            Select | None,
            Field(
                description="Faces by selection spec instead of indices, e.g. "
                "{'normal': [0,0,-1], 'max_angle': 60} for undersides, or a bounded "
                "position range for a colour band"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Put a material on an object, or on some of its faces (by index or by a
        selection spec: one call per colour region)."""
        return await blender.call(
            "assign_material", object=object, material=material, faces=faces,
            select=None if select is None else select.model_dump(exclude_none=True),
        )  # fmt: skip

    @mcp.tool()
    async def set_world(
        color: Color | None = None,
        strength: Annotated[float | None, Field(ge=0)] = None,
        hdri_path: Annotated[
            str | None, Field(description="Environment image (.hdr/.exr/...) in the workspace")
        ] = None,
        hdri_rotation: Annotated[float | None, Field(description="Degrees around Z")] = None,
    ) -> dict[str, Any]:
        """Set the world background: a flat color or an HDRI, and its strength
        (this lights the scene in EEVEE/Cycles)."""
        return await blender.call(
            "set_world", timeout=60, color=color, strength=strength, hdri_path=hdri_path,
            hdri_rotation=hdri_rotation,
        )  # fmt: skip

    @mcp.tool()
    async def look_at(
        name: Annotated[str, Field(description="Camera, light or any object")],
        target: Annotated[
            str | Annotated[list[float], Field(min_length=3, max_length=3)],
            Field(description="Object name or [x, y, z] point"),
        ],
    ) -> dict[str, Any]:
        """Rotate an object (usually a camera or light) so it points at a target."""
        return await blender.call("look_at", name=name, target=target)

    @mcp.tool()
    async def set_active_camera(name: str) -> dict[str, Any]:
        """Make this camera the scene camera (used by renders and 'camera' views)."""
        return await blender.call("set_active_camera", name=name)

    @mcp.tool()
    async def set_data_params(
        name: Annotated[str, Field(description="Object whose data to change")],
        params: Annotated[
            dict[str, Any],
            Field(
                description="Blender data properties, e.g. camera {'lens': 35, "
                "'type': 'ORTHO', 'ortho_scale': 5}, light {'energy': 500, "
                "'color': [1, 0.9, 0.8], 'shadow_soft_size': 0.5, 'spot_size': 45}. "
                "Angles in degrees. Unknown keys error with the valid list."
            ),
        ],
    ) -> dict[str, Any]:
        """Change settings on an object's data: camera lens, light power/color/size, etc."""
        return await blender.call("set_data_params", name=name, params=params)
