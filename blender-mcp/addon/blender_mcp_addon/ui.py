"""Preferences, operators and the sidebar panel.

No `from __future__ import annotations` here: Blender reads bpy.props from real
(non-string) class annotations.
"""

import bpy

from . import protocol, runtime

ADDON_ID = __package__


def get_prefs() -> "BlenderMCPPreferences | None":
    addon = bpy.context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None


class BlenderMCPPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    port: bpy.props.IntProperty(name="Port", default=protocol.DEFAULT_PORT, min=1024, max=65535)
    token: bpy.props.StringProperty(
        name="Token",
        description="Custom token (optional). Empty: a random token is kept in a private "
        "file that the server reads automatically. If set, give the server the same value "
        "in BLENDER_MCP_TOKEN",
        subtype="PASSWORD",
    )
    workspace: bpy.props.StringProperty(
        name="Workspace",
        description="Folder the agent may read and write files in "
        "(plus the open .blend's folder). Default: ~/BlenderMCP",
        subtype="DIR_PATH",
    )
    allow_python: bpy.props.BoolProperty(
        name="Allow arbitrary Python",
        description="Let the agent run any Python code in Blender (execute_python). The "
        "code runs with your user's full permissions",
        default=False,
    )
    auto_start: bpy.props.BoolProperty(
        name="Start automatically",
        description="Start listening when Blender starts",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "port")
        layout.prop(self, "token")
        layout.prop(self, "workspace")
        layout.prop(self, "auto_start")
        row = layout.row()
        row.alert = self.allow_python
        row.prop(self, "allow_python")
        layout.label(text=f"Token file: {protocol.token_file_path()}", icon="LOCKED")


class BLENDERMCP_OT_start(bpy.types.Operator):
    bl_idname = "blender_mcp.start"
    bl_label = "Start MCP Listener"
    bl_description = "Accept connections from the blender-mcp server"

    def execute(self, context):
        prefs = get_prefs()
        port = prefs.port if prefs else protocol.DEFAULT_PORT
        token = prefs.token if prefs else None
        workspace = bpy.path.abspath(prefs.workspace) if prefs and prefs.workspace else None
        allow_python = bool(prefs and prefs.allow_python)
        try:
            runtime.start(port=port, token=token, workspace=workspace, allow_python=allow_python)
        except OSError:
            self.report({"ERROR"}, runtime.last_error)
            return {"CANCELLED"}
        self.report({"INFO"}, runtime.status())
        return {"FINISHED"}


class BLENDERMCP_OT_copy_token(bpy.types.Operator):
    bl_idname = "blender_mcp.copy_token"
    bl_label = "Copy Token"
    bl_description = (
        "Copy the active token to the clipboard, for servers that can't read the token "
        "file (set it as BLENDER_MCP_TOKEN)"
    )

    def execute(self, context):
        prefs = get_prefs()
        try:
            token = (prefs.token if prefs else "") or protocol.ensure_token_file()
        except (protocol.TokenFileError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        context.window_manager.clipboard = token
        self.report({"INFO"}, "Token copied")
        return {"FINISHED"}


class BLENDERMCP_OT_stop(bpy.types.Operator):
    bl_idname = "blender_mcp.stop"
    bl_label = "Stop MCP Listener"

    def execute(self, context):
        runtime.stop()
        return {"FINISHED"}


class VIEW3D_PT_blender_mcp(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP"

    def draw(self, context):
        layout = self.layout
        running = runtime.is_running()
        layout.label(text=runtime.status(), icon="LINKED" if running else "UNLINKED")
        if runtime.last_error:
            layout.label(text=runtime.last_error, icon="ERROR")
        prefs = get_prefs()
        if running:
            layout.label(text=f"Auth: {runtime.token_source}", icon="LOCKED")
        if prefs and prefs.allow_python:
            layout.label(text="Arbitrary Python is ON", icon="ERROR")
        if running:
            layout.operator(BLENDERMCP_OT_stop.bl_idname, icon="PAUSE")
        else:
            layout.operator(BLENDERMCP_OT_start.bl_idname, icon="PLAY")
        if prefs:
            col = layout.column()
            col.enabled = not running
            col.prop(prefs, "port")
            col.prop(prefs, "token")
            col.prop(prefs, "workspace")
        layout.operator(BLENDERMCP_OT_copy_token.bl_idname, icon="COPYDOWN")


CLASSES = (
    BlenderMCPPreferences,
    BLENDERMCP_OT_start,
    BLENDERMCP_OT_stop,
    BLENDERMCP_OT_copy_token,
    VIEW3D_PT_blender_mcp,
)


def _auto_start():
    prefs = get_prefs()
    if prefs and prefs.auto_start and not runtime.is_running():
        try:
            workspace = bpy.path.abspath(prefs.workspace) if prefs.workspace else None
            runtime.start(
                port=prefs.port,
                token=prefs.token,
                workspace=workspace,
                allow_python=prefs.allow_python,
            )
        except OSError:
            pass  # surfaced in the panel via runtime.last_error
    return None


def _redraw_panels():
    # Keep the client count in the panel current.
    for window in bpy.context.window_manager.windows:
        if window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 1.0


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(runtime.drain_timer, persistent=True)
    if not bpy.app.background:
        bpy.app.timers.register(_redraw_panels, first_interval=1.0, persistent=True)
    bpy.app.timers.register(_auto_start, first_interval=0.5)


def unregister():
    runtime.stop()
    for timer in (runtime.drain_timer, _redraw_panels, _auto_start):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
