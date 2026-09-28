from godot_mcp.bbcode import first_paragraph, to_markdown


def test_references_and_formatting():
    text = (
        "Moves the body based on [member velocity]. See [method move_and_slide] and "
        "[CharacterBody2D]. [b]Note:[/b] use [code]delta[/code], [i]not[/i] frames. "
        "Arrays look like [lb]1, 2[rb]."
    )
    assert to_markdown(text) == (
        "Moves the body based on `velocity`. See `move_and_slide()` and `CharacterBody2D`. "
        "**Note:** use `delta`, *not* frames. Arrays look like [1, 2]."
    )


def test_code_blocks_keep_gdscript_drop_csharp():
    text = (
        "Example:\n[codeblocks]\n[gdscript]\nfunc _ready():\n\tprint(1)\n[/gdscript]\n"
        "[csharp]\npublic override void _Ready() {}\n[/csharp]\n[/codeblocks]\nDone."
    )
    md = to_markdown(text)
    assert "```gdscript\nfunc _ready():\n    print(1)\n```" in md
    assert "public override" not in md
    assert md.endswith("Done.")


def test_links_and_first_paragraph():
    assert to_markdown("[url=https://x.org]docs[/url]") == "docs (https://x.org)"
    assert first_paragraph("One.\nTwo.") == "One."
    assert first_paragraph("x" * 50, limit=10) == "x" * 9 + "…"
