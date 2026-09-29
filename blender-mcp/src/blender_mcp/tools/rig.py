"""Rigging and reference sheets."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel, ConfigDict, Field

from ._common import Blender
from .mesh import SELECT_HELP, Select, _spec

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]

CONVENTION = (
    " Conventions: Z up, the character faces -Y (Blender's front view), its left side is "
    "+X; left bones end in .L (on +X), right bones in .R."
)

LANDMARKS = (
    "hips, chest, neck, head, head_top (on the centre line, x=0); shoulder, elbow, "
    "wrist, hand_tip, hip_joint, knee, ankle, ball, toe (the character's LEFT side, x>0 — "
    "the right side is mirrored)"
)


class BoneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    head: Vec3 = Field(description="World position of the bone's start")
    tail: Vec3 = Field(description="World position of the bone's end")
    parent: str | None = Field(None, description="Must be listed earlier")
    connected: bool = Field(False, description="Head snaps to the parent's tail")
    roll: float = Field(0.0, description="Degrees")
    deform: bool = Field(True, description="False for control-only bones (e.g. root)")


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool(description="Create an armature from a list of bones." + CONVENTION)
    async def create_armature(
        bones: Annotated[list[BoneSpec], Field(min_length=1, max_length=256)],
        name: str = "Armature",
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await blender.call(
            "create_armature", name=name, collection=collection,
            bones=[b.model_dump() for b in bones],
        )  # fmt: skip

    @mcp.tool(
        description="Create a standard humanoid skeleton (root, hips, spine, chest, neck, "
        "head; shoulder/upper_arm/forearm/hand and thigh/shin/foot/toe per side) from body "
        "landmarks — measure them on the front/side reference sheet. Landmarks you omit use "
        "average proportions of `height`. Known landmarks: " + LANDMARKS + ". Add tails, "
        "ears, hair or props with extra_bones (same format as create_armature)." + CONVENTION
    )
    async def create_humanoid_rig(
        height: Annotated[float, Field(gt=0, description="Character height (units)")] = 1.8,
        landmarks: Annotated[
            dict[str, Vec3] | None, Field(description="World positions by landmark name")
        ] = None,
        extra_bones: list[BoneSpec] | None = None,
        name: str = "Rig",
        collection: str | None = None,
    ) -> dict[str, Any]:
        return await blender.call(
            "create_humanoid_rig", height=height, landmarks=landmarks, name=name,
            collection=collection,
            extra_bones=[b.model_dump() for b in extra_bones] if extra_bones else None,
        )  # fmt: skip

    @mcp.tool()
    async def bind_to_armature(
        ctx: Context,
        armature: str,
        meshes: Annotated[list[str], Field(min_length=1)],
        method: Annotated[
            Literal["automatic", "nearest"],
            Field(
                description="automatic: Blender's heat weights (smooth; gaps are filled with "
                "nearest). nearest: each vertex follows its closest 1-2 bones (robust for "
                "blocky low-poly and separate parts)"
            ),
        ] = "automatic",
        max_influences: Annotated[
            int,
            Field(
                ge=0,
                le=8,
                description="Keep each vertex's N strongest bones and normalise to 1 "
                "(4 = what game engines take; 0 = leave Blender's weights as they are)",
            ),
        ] = 4,
    ) -> dict[str, Any]:
        """Skin meshes to an armature: vertex groups per bone, an Armature modifier, and
        parenting (the Armature modifier goes first, before SUBSURF etc.). Binds in rest
        pose. Reports vertices per bone and any unweighted vertices — fix those with
        set_vertex_weights. Apply scale on the mesh first."""
        return await blender.call(
            "bind_to_armature", timeout=300, progress=ctx, armature=armature, meshes=meshes,
            method=method, max_influences=max_influences,
        )  # fmt: skip

    @mcp.tool(
        description="Set a bone's weight on selected vertices of a mesh (fix bad deformation "
        "around joints). normalize keeps each vertex's bone weights summing to 1." + SELECT_HELP
    )
    async def set_vertex_weights(
        mesh: str,
        group: Annotated[str, Field(description="Bone / vertex group name")],
        select: Select,
        weight: Annotated[float, Field(ge=0, le=1)] = 1.0,
        mode: Literal["REPLACE", "ADD", "SUBTRACT"] = "REPLACE",
        normalize: bool = True,
        type: Literal["verts", "edges", "faces"] = "verts",
    ) -> dict[str, Any]:
        return await blender.call(
            "set_vertex_weights", mesh=mesh, group=group, select=_spec(select), weight=weight,
            mode=mode, normalize=normalize, type=type,
        )  # fmt: skip

    @mcp.tool()
    async def pose_bone(
        armature: str,
        bone: str,
        rotation: Annotated[
            Vec3 | None,
            Field(
                description="Local Euler XYZ degrees. On create_humanoid_rig bones +X is the "
                "natural bend: spine/neck/head forward, arms/hands fold forward, knees back, "
                "toes down; thighs swing back (negative lifts the leg forward). Y twists "
                "along the bone (on spine/neck/head: +Y turns to the character's left). "
                "Z is sideways: head/spine tilt to the character's right; upper_arm.L +Z "
                "raises the arm (.R: -Z raises); thigh.L -Z spreads the leg out. Full "
                "table: blender://docs/rigging."
            ),
        ] = None,
        location: Vec3 | None = None,
        scale: Vec3 | float | None = None,
        frame: Annotated[
            float | None, Field(description="Also insert a keyframe at this frame")
        ] = None,
        mirror: Annotated[
            bool,
            Field(
                description="Also pose the opposite .L/.R bone symmetrically (X kept, Y/Z "
                "negated) — e.g. both arms down in one call"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Pose a bone to test deformation (then screenshot), or keyframe it for animation.
        Use reset_pose to return to the rest pose."""
        return await blender.call(
            "pose_bone", armature=armature, bone=bone, rotation=rotation, location=location,
            scale=scale, frame=frame, mirror=mirror,
        )  # fmt: skip

    @mcp.tool()
    async def reset_pose(armature: str) -> dict[str, Any]:
        """Put every bone back in its rest pose (keyframes stay)."""
        return await blender.call("reset_pose", armature=armature)

    @mcp.tool()
    async def get_armature_info(armature: str) -> dict[str, Any]:
        """Bones (world head/tail, parent), which are posed, and every bound mesh's weight
        summary: vertices per bone, unweighted vertices, bones with no vertices."""
        return await blender.call("get_armature_info", armature=armature)

    @mcp.tool()
    async def add_reference_image(
        path: Annotated[str, Field(description="Image in the workspace (see list_files)")],
        view: Literal["front", "side", "back"] = "front",
        character_height: Annotated[float, Field(gt=0)] = 1.8,
        pixel_top: Annotated[
            float | None, Field(ge=0, description="Image row of the top of the head")
        ] = None,
        pixel_bottom: Annotated[
            float | None, Field(ge=0, description="Image row of the soles of the feet")
        ] = None,
        pixel_center: Annotated[
            float | None,
            Field(
                ge=0,
                description="Image column of the body's centre line (front) or the "
                "ankle/centre of mass (side)",
            ),
        ] = None,
        crop: Annotated[
            list[float] | None,
            Field(
                min_length=4,
                max_length=4,
                description="[left, top, right, bottom] pixels: the region holding this "
                "view when one sheet has several views/poses side by side. pixel_top/"
                "bottom/center stay in full-image pixels. Default: the whole image",
            ),
        ] = None,
        facing: Annotated[
            Literal["left", "right"],
            Field(description="Side view: which way the character faces in the image"),
        ] = "left",
        opacity: Annotated[float, Field(gt=0, le=1)] = 1.0,
        distance: Annotated[
            float | None, Field(description="How far behind the model (default: height)")
        ] = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Put a reference image behind the model at true scale: the feet row lands on
        z=0 and the head row on z=character_height, centred on the model. Rows/columns are
        pixels from the image's top-left; without them the whole image height is the
        character. Re-adding the same name replaces it. Check alignment with
        render_preview(view='front' or 'right', ortho=true, textures=true)."""
        return await blender.call(
            "add_reference_image", path=path, view=view, character_height=character_height,
            pixel_top=pixel_top, pixel_bottom=pixel_bottom, pixel_center=pixel_center,
            crop=crop, facing=facing, opacity=opacity, distance=distance, name=name,
        )  # fmt: skip

    @mcp.tool()
    async def set_visibility(
        names: Annotated[list[str], Field(min_length=1)],
        viewport: bool | None = None,
        render: bool | None = None,
    ) -> dict[str, Any]:
        """Show or hide objects in the viewport and/or renders (e.g. hide reference planes
        for a clean render, or hide the rig)."""
        return await blender.call("set_visibility", names=names, viewport=viewport, render=render)
