"""Geometry Nodes: build a node graph on an object from a JSON description, inspect it,
and search node types."""

from __future__ import annotations

from typing import Any

import bpy

from .mesh_edit import _stats
from .undo import mutation
from .util import POINTER_LOOKUPS, get_object, rna_value, set_rna_props

MAX_NODES = 200
MODIFIER_NAME = "MCP Geometry Nodes"


def _node_types() -> list[tuple[str, str]]:
    """(bl_idname, UI name) for every Geometry Nodes node class."""
    found = []
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        if (
            isinstance(cls, type)
            and issubclass(cls, bpy.types.Node)
            and name.startswith(("GeometryNode", "FunctionNode", "ShaderNodeMath",
                                 "ShaderNodeVectorMath", "ShaderNodeCombineXYZ",
                                 "ShaderNodeSeparateXYZ", "ShaderNodeValue",
                                 "ShaderNodeMapRange", "ShaderNodeTexNoise"))
        ):  # fmt: skip
            found.append((name, cls.bl_rna.name))
    return sorted(found)


def find_node_types(params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query", "")).lower()
    words = query.split()
    matches = [
        {"type": ident, "name": label}
        for ident, label in _node_types()
        if all(w in (ident + " " + label).lower() for w in words)
    ]
    return {"count": len(matches), "types": matches[:60]}


def _socket(sockets: Any, spec: str, node: bpy.types.Node, kind: str) -> Any:
    """A socket by name, by name#n (n-th socket with that name), or by index."""
    visible = [s for s in sockets if s.enabled]
    if spec.isdigit():
        index = int(spec)
        if index < len(visible):
            return visible[index]
    else:
        name, _, nth = spec.partition("#")
        same = [s for s in visible if s.name == name or s.identifier == name]
        n = int(nth) if nth.isdigit() else 0
        if n < len(same):
            return same[n]
    names = [s.name for s in visible]
    raise ValueError(f"node {node.name!r} has no {kind} socket {spec!r}; {kind}s: {names}")


def _endpoint(tree: bpy.types.NodeTree, ref: str, kind: str) -> Any:
    if "." not in ref:
        raise ValueError(f"link endpoint {ref!r} must look like 'Node Name.Socket'")
    node_name, socket = ref.rsplit(".", 1)
    node = tree.nodes.get(node_name)
    if node is None:
        raise ValueError(f"no node named {node_name!r}; nodes: {[n.name for n in tree.nodes]}")
    return _socket(node.outputs if kind == "output" else node.inputs, socket, node, kind)


def _set_socket_value(socket: Any, value: Any) -> None:
    if not hasattr(socket, "default_value"):
        raise ValueError(f"socket {socket.name!r} has no value to set")
    kind = socket.type
    lookup = {
        "OBJECT": "Object", "MATERIAL": "Material", "COLLECTION": "Collection",
        "IMAGE": "Image",
    }.get(kind)  # fmt: skip
    if lookup is not None:
        found = POINTER_LOOKUPS[lookup]().get(value) if value is not None else None
        if value is not None and found is None:
            raise ValueError(f"socket {socket.name!r}: no {lookup} named {value!r}")
        value = found
    try:
        socket.default_value = value
    except (TypeError, ValueError) as exc:
        raise ValueError(f"socket {socket.name!r}: {exc}") from None


def _describe_node(node: bpy.types.Node) -> dict[str, Any]:
    def sockets(items: Any) -> list[Any]:
        out = []
        for s in items:
            if not s.enabled:
                continue
            entry: dict[str, Any] = {"name": s.name, "type": s.type}
            if s.is_linked:
                entry["linked"] = True
            elif hasattr(s, "default_value") and s.type not in {"GEOMETRY"}:
                entry["value"] = rna_value(s.default_value)
            out.append(entry)
        return out

    return {
        "name": node.name,
        "type": node.bl_idname,
        "inputs": sockets(node.inputs),
        "outputs": sockets(node.outputs),
    }


def _describe_tree(tree: bpy.types.NodeTree) -> dict[str, Any]:
    return {
        "group": tree.name,
        "nodes": [_describe_node(n) for n in tree.nodes],
        "links": [
            f"{link.from_node.name}.{link.from_socket.name} -> "
            f"{link.to_node.name}.{link.to_socket.name}"
            for link in tree.links
        ],
    }


def _new_tree(name: str) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    group_in = tree.nodes.new("NodeGroupInput")
    group_in.name = "Group Input"
    group_in.location = (-400, 0)
    group_out = tree.nodes.new("NodeGroupOutput")
    group_out.name = "Group Output"
    group_out.location = (600, 0)
    return tree


@mutation("build geometry nodes")
def build_geometry_nodes(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    nodes = params.get("nodes") or []
    links = params.get("links") or []
    if len(nodes) > MAX_NODES:
        raise ValueError(f"at most {MAX_NODES} nodes")
    tree = _new_tree(params.get("group_name") or f"{obj.name} Nodes")
    try:
        for i, spec in enumerate(nodes):
            if not isinstance(spec, dict) or "type" not in spec or "name" not in spec:
                raise ValueError("each node needs 'name' and 'type' (e.g. GeometryNodeMeshCube)")
            if spec["name"] in ("Group Input", "Group Output") or tree.nodes.get(spec["name"]):
                raise ValueError(f"duplicate or reserved node name {spec['name']!r}")
            try:
                node = tree.nodes.new(spec["type"])
            except RuntimeError:
                raise ValueError(
                    f"unknown node type {spec['type']!r}; use find_node_types to search"
                ) from None
            node.name = spec["name"]
            node.location = spec.get("location") or (i * 200 - 200, -200 * (i % 2))
            if spec.get("properties"):
                set_rna_props(node, spec["properties"])  # e.g. data_type, domain, mode
            for key, value in (spec.get("inputs") or {}).items():
                _set_socket_value(_socket(node.inputs, str(key), node, "input"), value)
        for link in links:
            if not isinstance(link, list | tuple) or len(link) != 2:
                raise ValueError("each link is ['From Node.Output', 'To Node.Input']")
            tree.links.new(_endpoint(tree, link[0], "output"), _endpoint(tree, link[1], "input"))
    except Exception:
        bpy.data.node_groups.remove(tree)
        raise

    replace = params.get("replace", True)
    mod = obj.modifiers.get(MODIFIER_NAME) if replace else None
    old_group = mod.node_group if mod else None
    if mod is None:
        mod = obj.modifiers.new(MODIFIER_NAME, "NODES")
    mod.node_group = tree
    if old_group is not None and old_group.users == 0:
        bpy.data.node_groups.remove(old_group)

    result = {"object": obj.name, "modifier": mod.name, **_describe_tree(tree)}
    if obj.type == "MESH":
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            result["evaluated"] = {"vertices": len(mesh.vertices), "faces": len(mesh.polygons)}
        finally:
            evaluated.to_mesh_clear()
        result["base_mesh"] = _stats(obj)
    return result


def get_geometry_nodes(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    groups = [
        {"modifier": m.name, **_describe_tree(m.node_group)}
        for m in obj.modifiers
        if m.type == "NODES" and m.node_group is not None
    ]
    return {"object": obj.name, "node_modifiers": groups}
