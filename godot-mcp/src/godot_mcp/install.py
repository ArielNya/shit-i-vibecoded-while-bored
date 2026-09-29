"""`godot-mcp install-addon <project>`: copy this server's plugin into a Godot project and
enable it, so a real project is one command away from being usable."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from .headless import HeadlessError, addon_dir

PLUGIN_CFG = "res://addons/godot_mcp/plugin.cfg"


def plugin_version(folder: Path) -> str | None:
    cfg = folder / "plugin.cfg"
    if not cfg.is_file():
        return None
    match = re.search(r'^version="([^"]*)"', cfg.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else "?"


def enable_plugin(project_godot: Path) -> bool:
    """Adds the plugin to [editor_plugins] enabled=...; False if it already was."""
    text = project_godot.read_text(encoding="utf-8")
    if PLUGIN_CFG in text:
        return False
    line = f'enabled=PackedStringArray("{PLUGIN_CFG}")'
    section = re.search(r"^\[editor_plugins\][ \t]*$", text, re.MULTILINE)
    if section is None:
        text = text.rstrip("\n") + f"\n\n[editor_plugins]\n\n{line}\n"
    else:
        existing = re.compile(r"^enabled=PackedStringArray\((.*)\)[ \t]*$", re.MULTILINE)
        match = existing.search(text, section.end())
        next_section = re.search(r"^\[", text[section.end() :], re.MULTILINE)
        end = section.end() + next_section.start() if next_section else len(text)
        if match and match.start() < end:
            items = match.group(1).strip()
            joined = f'{items}, "{PLUGIN_CFG}"' if items else f'"{PLUGIN_CFG}"'
            text = (
                text[: match.start()] + f"enabled=PackedStringArray({joined})" + text[match.end() :]
            )
        else:
            text = text[: section.end()] + f"\n\n{line}" + text[section.end() :]
    project_godot.write_text(text, encoding="utf-8")
    return True


def install(project: Path) -> list[str]:
    """Installs or updates addons/godot_mcp in `project`; returns what happened."""
    project = project.expanduser().resolve()
    if project.name == "project.godot":
        project = project.parent
    project_godot = project / "project.godot"
    if not project_godot.is_file():
        raise HeadlessError(f"No project.godot in '{project}'.")
    source = addon_dir()
    target = project / "addons" / "godot_mcp"
    old, new = plugin_version(target), plugin_version(source)
    if target.is_symlink():
        raise HeadlessError(f"'{target}' is a symlink (a dev setup?); not replacing it.")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.import"))
    done = [f"Updated the plugin {old} -> {new}" if old else f"Installed the plugin {new}",
            f"  in {target}"]  # fmt: skip
    if enable_plugin(project_godot):
        done.append("Enabled it in project.godot ([editor_plugins]).")
    return done


def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser(
        prog="godot-mcp install-addon",
        description="Copy the Godot MCP plugin into a Godot project and enable it.",
    )
    p.add_argument("project", nargs="?", default=".", help="project folder (default: .)")
    args = p.parse_args(argv)
    try:
        for line in install(Path(args.project)):
            print(line)
    except HeadlessError as exc:
        sys.exit(f"install-addon: {exc}")
    print(
        "\nNext: open the project in Godot 4.7+ (if it is already open, use Project > Reload "
        "Current Project). The MCP dock shows 'Listening on 127.0.0.1:9080'. Then register "
        "the server with your MCP client (see the godot-mcp README), e.g. for Claude Code:\n"
        '  claude mcp add godot -- uvx --from "git+https://github.com/ArielNya/'
        'shit-i-vibecoded-while-bored@main#subdirectory=godot-mcp" godot-mcp'
    )
