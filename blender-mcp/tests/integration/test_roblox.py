"""Roblox avatar assets: bake to one texture, spec checks, the Roblox FBX export."""

import pytest

pytestmark = pytest.mark.anyio

HAT_ATT = [0, 0, 0]


async def test_rigid_hat_bake_check_export(call, call_error, workspace):
    await call("delete_objects", names=["Cube"])
    await call("create_primitive", type="cylinder", name="Hat", radius=0.8, depth=0.5)
    await call("create_primitive", type="cone", name="Top", radius=0.4, depth=0.6,
               location=[0, 0, 0.55])  # fmt: skip
    await call("create_material", name="Black", base_color=[0.02, 0.02, 0.02])
    await call("create_material", name="Gold", base_color=[1, 0.8, 0.1])
    await call("assign_material", object="Hat", material="Black")
    await call("assign_material", object="Top", material="Gold")
    await call("join_objects", names=["Hat", "Top"])

    before = await call("check_roblox_asset", object="Hat", attachment=HAT_ATT)
    assert not before["ok"]
    assert any("2 materials" in e for e in before["errors"])

    baked = await call("bake_texture", object="Hat", path="hat.png", size=256)
    assert baked["size"] == [256, 256] and (workspace / "hat.png").is_file()
    assert sorted(baked["replaced_materials"]) == ["Black", "Gold"]

    report = await call("check_roblox_asset", object="Hat", attachment=HAT_ATT)
    assert report["ok"], report["errors"]
    hat = report["objects"]["Hat"]
    assert hat["materials"] == 1 and hat["uv_maps"] == 1
    assert hat["textures"][0]["size"] == [256, 256]
    assert hat["roblox_attachment"] == "HatAttachment"
    # bounds z -0.25..0.85: the attachment sits 0.3 below the Handle's centre
    assert hat["handle_attachment_position"] == pytest.approx([0, -0.3, 0], abs=1e-3)

    # Wider than a Normal hat (1.87 studs) but fine for Classic (3).
    await call("transform_object", name="Hat", scale=[1.5, 1.5, 1], mode="set")
    await call("apply_transform", name="Hat")
    wide = await call("check_roblox_asset", object="Hat", attachment=HAT_ATT)
    assert any("left/right" in e for e in wide["errors"])
    classic = await call("check_roblox_asset", object="Hat", attachment=HAT_ATT,
                         body_scale="classic")  # fmt: skip
    assert classic["ok"], classic["errors"]

    out = await call("export_file", path="hat.fbx", objects=["Hat"], roblox=True)
    assert out["bytes"] > 0
    data = (workspace / "hat.fbx").read_bytes()
    assert b"hat.png" in data and len(data) > 256 * 256 // 50  # the texture is embedded

    # Round trip: FBX Unit Scale keeps 1 unit = 1 stud.
    await call("delete_objects", names=["Hat"])
    imported = await call("import_file", path="hat.fbx")
    info = await call("get_object_info", name=imported["objects"][0])
    assert abs(max(info["dimensions"]) - 2.4) < 0.01


async def test_layered_and_body_report_whats_missing(call):
    await call("create_primitive", type="cube", name="Shirt", size=2)
    layered = await call("check_roblox_asset", kind="layered", object="Shirt")
    errors = " ".join(layered["errors"])
    assert "Shirt_InnerCage" in errors and "Shirt_OuterCage" in errors
    assert any("AutoSkin" in w for w in layered["warnings"])  # skinning is optional

    body = await call("check_roblox_asset", kind="body")
    assert not body["ok"]
    assert any("Head_Geo" in e for e in body["errors"])
    assert any("Hat_Att" in e for e in body["errors"])
