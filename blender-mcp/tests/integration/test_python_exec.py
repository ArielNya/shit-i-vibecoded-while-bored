"""M5: execute_python, in a Blender started with --allow-python and a token."""

import pytest

pytestmark = pytest.mark.anyio

BLENDER_OPTIONS = {"token": "test-token", "allow_python": True}


async def test_result_and_stdout(call):
    out = await call(
        "execute_python",
        code=(
            "bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 3))\n"
            "obj = C.active_object\n"
            "obj.name = 'Scripted'\n"
            "print('made', obj.name)\n"
            "result = {'name': obj.name, 'location': obj.location, 'data': obj.data}\n"
        ),
    )
    assert out["stdout"] == "made Scripted\n"
    assert out["result"]["name"] == "Scripted"
    assert out["result"]["location"] == [0.0, 0.0, 3.0]
    assert out["result"]["data"].startswith("Cube")  # IDs come back as their names
    listed = await call("list_objects", name_contains="Scripted")
    assert listed["total"] == 1
    await call("delete_objects", names=["Scripted"])


async def test_result_conversions(call):
    out = await call(
        "execute_python",
        code="result = [Vector((1, 2, 3)), Matrix.Identity(2), D.objects['Camera'], 1.5, None]",
    )
    assert out["result"] == [[1.0, 2.0, 3.0], [[1.0, 0.0], [0.0, 1.0]], "Camera", 1.5, None]


async def test_errors_show_the_failing_line_and_prior_output(call_error):
    text = await call_error(
        "execute_python", code="print('before')\nx = 1\nraise ValueError('boom')\n"
    )
    assert "line 3" in text and "ValueError: boom" in text
    assert "before" in text

    text = await call_error("execute_python", code="def broken(:\n    pass")
    assert "SyntaxError" in text and "line 1" in text


async def test_exit_does_not_stop_blender(call, call_error):
    text = await call_error("execute_python", code="import sys\nsys.exit(3)")
    assert "SystemExit" in text
    assert (await call("ping"))["pong"] is True  # Blender is still serving requests


async def test_sessions(call, call_error):
    await call("execute_python", code="counter = 1", keep_session=True)
    out = await call("execute_python", code="counter += 1\nresult = counter", keep_session=True)
    assert out["result"] == 2
    # Without keep_session every run starts fresh.
    assert "NameError" in await call_error("execute_python", code="result = counter")
    assert "NameError" in await call_error(
        "execute_python", code="result = counter", keep_session=True, reset_session=True
    )


async def test_long_output_is_clipped(call):
    out = await call("execute_python", code="print('x' * 50_000)")
    assert len(out["stdout"]) < 21_000
    assert "more characters cut" in out["stdout"]


async def test_one_run_is_one_undo_step(call):
    await call(
        "execute_python",
        code=(
            "for i in range(3):\n"
            "    o = D.objects.new(f'Batch{i}', None)\n"
            "    C.scene.collection.objects.link(o)\n"
        ),
    )
    assert (await call("list_objects", name_contains="Batch"))["total"] == 3
    await call("undo")
    assert (await call("list_objects", name_contains="Batch"))["total"] == 0


async def test_import_cleanup_classifies_file_backed_data(call, workspace, tmp_path_factory):
    """After an import, file-backed datablocks pointing outside the allowed folders are
    removed (binary formats like .fbx/.usd can't be pre-scanned). This checks the
    classification that decides it, on images loaded from inside and outside."""
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.png"
    inside = workspace / "fine.png"
    for path in (outside, inside):
        path.write_bytes(b"not decoded until used")
    out = await call(
        "execute_python",
        code=(
            "from blender_mcp_addon.handlers import files\n"
            f"a = D.images.load({str(outside)!r}, check_existing=False)\n"
            f"b = D.images.load({str(inside)!r}, check_existing=False)\n"
            "g = D.images.new('generated', 4, 4)\n"
            "result = [files._outside_file(a), files._outside_file(b), files._outside_file(g)]\n"
            "for img in (a, b, g): D.images.remove(img)\n"
        ),
    )
    assert out["result"] == [str(outside.resolve()), None, None]
