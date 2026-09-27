from __future__ import annotations

from typing import Any

import bpy

from .util import get_material, rna_value

MAX_NODES = 100


def _users_by_material() -> dict[str, list[str]]:
    users: dict[str, list[str]] = {}
    for obj in bpy.context.scene.objects:
        for slot in obj.material_slots:
            if slot.material:
                users.setdefault(slot.material.name, []).append(obj.name)
    return users


def _principled(mat: bpy.types.Material) -> bpy.types.Node | None:
    if not mat.use_nodes or not mat.node_tree:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _socket_value(socket: bpy.types.NodeSocket) -> Any:
    if socket.is_linked:
        link = socket.links[0]
        return {"linked_from": f"{link.from_node.name}.{link.from_socket.name}"}
    if hasattr(socket, "default_value"):
        return rna_value(socket.default_value)
    return None


def list_materials(params: dict[str, Any]) -> dict[str, Any]:
    users = _users_by_material()
    materials = []
    for mat in sorted(bpy.data.materials, key=lambda m: m.name):
        entry: dict[str, Any] = {
            "name": mat.name,
            "use_nodes": mat.use_nodes,
            "objects": users.get(mat.name, []),
            "fake_user": mat.use_fake_user,
        }
        bsdf = _principled(mat)
        if bsdf is not None:
            entry["base_color"] = _socket_value(bsdf.inputs["Base Color"])
            entry["metallic"] = _socket_value(bsdf.inputs["Metallic"])
            entry["roughness"] = _socket_value(bsdf.inputs["Roughness"])
        else:
            entry["diffuse_color"] = rna_value(mat.diffuse_color)
        materials.append(entry)
    return {"count": len(materials), "materials": materials}


def get_material_info(params: dict[str, Any]) -> dict[str, Any]:
    mat = get_material(params["name"])
    info: dict[str, Any] = {
        "name": mat.name,
        "use_nodes": mat.use_nodes,
        "objects": _users_by_material().get(mat.name, []),
        "diffuse_color": rna_value(mat.diffuse_color),
        "metallic": rna_value(mat.metallic),
        "roughness": rna_value(mat.roughness),
        "blend": getattr(mat, "surface_render_method", None) or getattr(mat, "blend_method", None),
    }
    bsdf = _principled(mat)
    if bsdf is not None:
        info["principled_bsdf"] = {
            socket.name: _socket_value(socket)
            for socket in bsdf.inputs
            if socket.enabled and hasattr(socket, "default_value")
        }
    if mat.use_nodes and mat.node_tree:
        nodes = list(mat.node_tree.nodes)
        info["nodes"] = [
            {"name": n.name, "type": n.type, **({"label": n.label} if n.label else {})}
            for n in nodes[:MAX_NODES]
        ]
        if len(nodes) > MAX_NODES:
            info["nodes_truncated"] = len(nodes) - MAX_NODES
        info["links"] = [
            f"{link.from_node.name}.{link.from_socket.name} -> "
            f"{link.to_node.name}.{link.to_socket.name}"
            for link in mat.node_tree.links
        ][: MAX_NODES * 2]
    return info
