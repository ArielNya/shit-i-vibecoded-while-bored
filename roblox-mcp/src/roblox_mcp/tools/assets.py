"""Uploading local files (models, images, audio, video, animations) to Roblox through the
Open Cloud Assets API, with a manifest so unchanged files are never uploaded twice."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import opencloud
from .project import inside

MANIFEST = "assets.lock.json"
MAX_BYTES = 20 * 1024 * 1024  # per upload (creator-docs cloud/guides/usage-assets.md)

# extension -> (default asset type, content type); from the docs' supported-types table
TYPES = {
    ".fbx": ("Model", "model/fbx"),
    ".gltf": ("Model", "model/gltf+json"),
    ".glb": ("Model", "model/gltf-binary"),
    ".rbxm": ("Model", "model/x-rbxm"),
    ".rbxmx": ("Model", "model/x-rbxm"),
    ".png": ("Image", "image/png"),
    ".jpg": ("Image", "image/jpeg"),
    ".jpeg": ("Image", "image/jpeg"),
    ".bmp": ("Image", "image/bmp"),
    ".tga": ("Image", "image/tga"),
    ".mp3": ("Audio", "audio/mpeg"),
    ".ogg": ("Audio", "audio/ogg"),
    ".wav": ("Audio", "audio/wav"),
    ".flac": ("Audio", "audio/flac"),
    ".mp4": ("Video", "video/mp4"),
    ".mov": ("Video", "video/mov"),
}
# asset types a file may be uploaded as instead of its default
ALTERNATIVES = {
    **dict.fromkeys((".rbxm", ".rbxmx"), {"Animation"}),
    **dict.fromkeys((".png", ".jpg", ".jpeg", ".bmp", ".tga"), {"Decal"}),
}
# where the id goes once uploaded
USE = {
    "Model": "insert it with Studio's insert_asset (a Model of MeshParts)",
    "Animation": "set Animation.AnimationId, then Animator:LoadAnimation",
    "Image": "set a Content property to Content.fromAssetId(asset_id): "
    "ImageLabel.ImageContent, Decal.ColorMapContent, MeshPart.TextureContent "
    "(Decal.Texture is deprecated)",
    "Decal": "insert it with Studio's insert_asset",
    "Audio": "set Sound.SoundId (or AudioPlayer.Asset) to the uri",
    "Video": "set VideoFrame.Video / VideoPlayer.VideoContent to the uri",
}


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    text = json.dumps(dict(sorted(manifest.items())), indent=2) + "\n"
    (root / MANIFEST).write_text(text, encoding="utf-8")


def creator() -> dict[str, int]:
    group, user = (
        os.environ.get("ROBLOX_CREATOR_GROUP_ID"),
        os.environ.get("ROBLOX_CREATOR_USER_ID"),
    )
    if group:
        return {"groupId": int(group)}
    if user:
        return {"userId": int(user)}
    raise opencloud.CloudError("set ROBLOX_CREATOR_USER_ID (your user id) or "
                               "ROBLOX_CREATOR_GROUP_ID (a group's) to own uploads")  # fmt: skip


def entry_result(relative: str, entry: dict[str, Any], cached: bool) -> dict[str, Any]:
    return {
        "file": relative,
        "asset_id": entry["asset_id"],
        "uri": f"rbxassetid://{entry['asset_id']}",
        "asset_type": entry["asset_type"],
        "moderation": entry.get("moderation"),
        "cached": cached,
        "use": USE[entry["asset_type"]],
    }


def upload(root: Path, path: str, name: str, description: str, asset_type: str) -> dict:
    file = inside(root, path)
    if not file.is_file():
        raise ValueError(f"'{path}' is not a file in the project")
    ext = file.suffix.lower()
    if ext not in TYPES:
        raise ValueError(f"can't upload {ext or 'files without an extension'}; supported: "
                         f"{', '.join(TYPES)}")  # fmt: skip
    default_type, content_type = TYPES[ext]
    asset_type = asset_type or default_type
    if asset_type != default_type and asset_type not in ALTERNATIVES.get(ext, set()):
        others = "".join(f" or {t}" for t in sorted(ALTERNATIVES.get(ext, ())))
        raise ValueError(f"a {ext} file can be uploaded as {default_type}{others}")
    data = file.read_bytes()
    if len(data) > MAX_BYTES and asset_type != "Video":
        raise ValueError(f"{len(data) // 1024 // 1024} MB is over Open Cloud's 20 MB limit")
    relative = str(file.relative_to(root))
    digest = hashlib.sha256(data).hexdigest()
    manifest = read_manifest(root)
    known = manifest.get(relative)
    if known and known["sha256"] == digest and known["asset_type"] == asset_type:
        return entry_result(relative, known, cached=True)
    asset = opencloud.create_asset(
        {
            "assetType": asset_type,
            "displayName": (name or file.stem)[:50],
            "description": description[:1000],
            "creationContext": {"creator": creator()},
        },
        file.name.replace('"', ""),
        content_type,
        data,
    )
    asset_id = int(asset["assetId"])
    entry = {
        "sha256": digest,
        "asset_id": asset_id,
        "asset_type": asset_type,
        "moderation": (asset.get("moderationResult") or {}).get("moderationState")
        or opencloud.moderation_state(asset_id),
        "uploaded": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    }
    manifest[relative] = entry
    write_manifest(root, manifest)
    result = entry_result(relative, entry, cached=False)
    if ext == ".gltf":
        result["note"] = ("only this .gltf file was uploaded; external .bin/texture files "
                          "aren't. Prefer .glb, which embeds them.")  # fmt: skip
    return result


def list_uploaded(root: Path, refresh: bool) -> dict[str, Any]:
    manifest = read_manifest(root)
    if refresh:
        for entry in manifest.values():
            entry["moderation"] = opencloud.moderation_state(entry["asset_id"])
        write_manifest(root, manifest)
    assets = []
    for relative, entry in sorted(manifest.items()):
        file = root / relative
        changed = (not file.is_file()
                   or hashlib.sha256(file.read_bytes()).hexdigest() != entry["sha256"])  # fmt: skip
        assets.append({**entry_result(relative, entry, cached=True), "file_changed": changed})
    return {"manifest": MANIFEST, "assets": assets}


def register(mcp: MCPServer, root: Path) -> None:
    @mcp.tool()
    def upload_asset(
        path: Annotated[str, Field(description="File in the project, e.g. assets/sword.glb")],
        name: Annotated[str, Field(description="Display name (default: file name)")] = "",
        description: Annotated[str, Field(description="Asset description")] = "",
        asset_type: Annotated[
            str,
            Field(
                description='Override the type: "Animation" for .rbxm/.rbxmx, '
                '"Decal" for images (default: from the extension)'
            ),  # fmt: skip
        ] = "",
    ) -> dict[str, Any]:
        """Upload a local model (.fbx/.glb/.gltf/.rbxm), image, audio or video file to
        Roblox with Open Cloud and return its rbxassetid:// plus how to use it (models: Studio's
        insert_asset). Unchanged files already uploaded return their recorded id without
        uploading again (assets.lock.json). New assets may be in moderation for a while."""
        return upload(root, path, name, description, asset_type)

    @mcp.tool()
    def list_uploaded_assets(
        refresh: Annotated[bool, Field(description="Re-check moderation with Open Cloud")] = False,
    ) -> dict[str, Any]:
        """Assets uploaded from this project (assets.lock.json): file, asset id, type,
        moderation state, and whether the file changed since it was uploaded."""
        return list_uploaded(root, refresh)
