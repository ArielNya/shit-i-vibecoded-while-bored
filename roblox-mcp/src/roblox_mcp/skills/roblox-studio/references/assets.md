# Assets

Sources: creator-docs `cloud/guides/usage-assets.md` and `reference/cloud/assets/v1.json`
(Open Cloud Assets API); property names checked against the Engine API reference for
Studio 0.740.

## Which route

| You have | Do |
| --- | --- |
| Something on the Creator Store | Studio's `search_asset` → `insert_asset` |
| Nothing yet, want a prop | Studio's `generate_mesh` / `generate_procedural_model`, or build it from parts with `execute_luau` |
| A local file (`.glb`, `.fbx`, `.png`, `.ogg`, ...) | roblox-mcp `upload_asset` → use the returned id (below) |
| An image on the web | Studio's `upload_image` (takes URLs) |

## upload_asset

- Types from the extension: `.fbx .gltf .glb .rbxm .rbxmx` → Model, `.png .jpg .jpeg
  .bmp .tga` → Image, `.mp3 .ogg .wav .flac` → Audio, `.mp4 .mov` → Video.
  `asset_type="Animation"` for an `.rbxm`/`.rbxmx` animation, `"Decal"` for an image
  you want as a Decal asset.
- Limits: 20 MB per file; images under 8000×8000; audio up to 7 minutes and **10 uploads
  a month (100 if ID-verified)**; video up to 5 minutes, 20 a day. Don't upload
  throwaway versions of audio.
- Prefer `.glb` over `.gltf`: only the one file is uploaded, so a `.gltf` loses its
  external `.bin` and textures.
- Models arrive as a `Model` containing `MeshPart`s. `.rbxm`/`.rbxmx` models are uploaded
  as packages. Models edited outside Studio might not upload.
- Needs `ROBLOX_API_KEY` (scopes `asset:read`, `asset:write`) and the owner:
  `ROBLOX_CREATOR_USER_ID` or `ROBLOX_CREATOR_GROUP_ID` (a group upload needs a key
  created with that group's asset permissions).
- Every upload is recorded in `assets.lock.json` (path, content hash, id). Uploading an
  unchanged file returns the recorded id without uploading again. Commit the manifest.
- New assets start in moderation (`Reviewing`) and may not load until `Approved`;
  `list_uploaded_assets refresh=true` re-checks. `Rejected` means replace the file.

## Using the id

| Type | Where it goes |
| --- | --- |
| Model | Studio's `insert_asset(asset_id)`, then position it with `execute_luau` (undoable) |
| Image | `Content` properties: `Content.fromAssetId(id)` into `ImageLabel.ImageContent`, `Decal.ColorMapContent`, `MeshPart.TextureContent`. `Decal.Texture` is deprecated |
| Audio | `Sound.SoundId = "rbxassetid://id"` (or `AudioPlayer.Asset`) |
| Video | `VideoFrame.Video` / `VideoFrame.VideoContent` |
| Animation | `Animation.AnimationId`, then `Animator:LoadAnimation(animation)` |

After inserting anything, look inside it (`search_game_tree` on the new instance): a
model can carry scripts, and imported meshes can arrive at odd scales or orientations.
