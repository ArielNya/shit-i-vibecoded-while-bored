"""Run the same Roblox tasks with and without the roblox-studio skill and grade the result.

    ROBLOX_MCP_BIN_DIR=... uv run python evals/run_evals.py [--runs 2] [--tasks shop,sign]

Each run: a fresh project from init_project, Claude Code (`claude -p`) with only
roblox-mcp connected. "with": the skill installed in the project. "without": no skill and
read_guide blocked. Grading is automatic: check_code errors, deprecated APIs, specs, and
task-specific safety checks (below). Writes evals/results/<date>.json and .md."""

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from roblox_mcp.tools import code, project, tests

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src/roblox_mcp/skills/roblox-studio"

# Old APIs agents like to write (on top of luau-lsp's DeprecatedApi warnings).
DEPRECATED = {
    "wait()": r"(?<![\w.:])wait\s*\(",
    "spawn()": r"(?<![\w.:])spawn\s*\(",
    "delay()": r"(?<![\w.:])delay\s*\(",
    "Body* movers": r"\bBody(Velocity|Gyro|Position|AngularVelocity|Force)\b",
    "Humanoid:LoadAnimation": r"[Hh]umanoid:LoadAnimation",
    "PhysicsService collision groups": r"PhysicsService:(Register|CollisionGroupSet)Coll",
    "LoadCharacter()": r":LoadCharacter\s*\(",
}  # fmt: skip

TASKS = {
    "shop": {
        "prompt": "Add a shop to this Roblox game. Players have Coins shown on the "
        "leaderboard (start with 100). Clients ask to buy an item by id and quantity "
        "through a RemoteEvent; the server owns the prices (Sword 50, Potion 10) and the "
        "coins. Write unit tests for the purchase logic.",
        "checks": {
            "validates remote arg types": r"\b(typeof|type)\s*\(",
            "rejects NaN/inf or fractional quantities": r"math\.isfinite|math\.floor|%\s*1\s*[~=]=",
        },
        "needs_tests": True,
    },
    "sign": {
        "prompt": "Add a sign in the workspace that shows a message. Players type a message "
        "in a TextBox on screen and press a button; the message then shows on the sign "
        "for everyone.",
        "checks": {
            "filters text (FilterStringAsync)": r"FilterStringAsync",
            "broadcast filter": r"GetNonChatStringForBroadcastAsync",
            "limits message length": r"#\w+\s*>|(string|utf8)\.len|:len\(|(string\.|:)sub\(",
        },
        "needs_tests": False,
    },
    "projectile": {
        "prompt": "Add a fireball: when a player presses F, the server launches a glowing "
        "ball from their character in the direction they're facing. It flies in a straight "
        "line, passes through other players' fireballs and its owner, damages the first "
        "other player it hits by 25, and disappears after 3 seconds.",
        "checks": {
            "excludes owner and other fireballs": r"CollisionGroup|FilterDescendantsInstances",
            "server-side cooldown": r"os\.clock|tick\(|time\(|DateTime|cooldown|Cooldown",
        },
        "needs_tests": False,
    },
    "npc": {
        "prompt": "Add a guard NPC (an R15 rig already in workspace named Guard, with an "
        "Animation named Walk inside it) that walks between the parts tagged "
        '"Waypoint" in order, forever, playing the walk animation while it moves and '
        "going around obstacles.",
        "checks": {
            "animates through the Animator": r"Animator",
            "uses pathfinding": r"PathfindingService",
            "handles failed paths": r"Status|Blocked|pcall",
        },
        "needs_tests": False,
    },
    "save": {
        "prompt": "Save each player's Coins (a leaderstats value) between sessions using "
        "DataStores.",
        "checks": {
            "pcall around data store calls": r"pcall",
            "saves on server shutdown (BindToClose)": r"BindToClose",
            "saves when the player leaves": r"PlayerRemoving",
        },
        "needs_tests": False,
    },
}


def luau_files(game: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted((game / "src").rglob("*.luau"))
        if not p.name.endswith(".spec.luau")
    )


def grade(game: Path, task: dict) -> dict:
    check = code.check(game, "")
    source = luau_files(game)
    deprecated = [n for n, rx in DEPRECATED.items() if re.search(rx, source)]
    deprecated += [p for p in check["problems"] if "DeprecatedApi" in p]
    result = {
        "type_errors": check["errors"],
        "deprecated": deprecated,
        "checks": {name: bool(re.search(rx, source)) for name, rx in task["checks"].items()},
    }
    if task["needs_tests"]:
        run = tests.run_local(game, "", "")
        result["tests"] = f"{run['passed']} passed, {run['failed']} failed"
        result["tests_ok"] = run["passed"] > 0 and run["failed"] == 0
    passed = [result["type_errors"] == 0, not deprecated, *result["checks"].values()]
    if task["needs_tests"]:
        passed.append(result["tests_ok"])
    result["score"] = f"{sum(passed)}/{len(passed)}"
    result["all_pass"] = all(passed)
    return result


def run_one(name: str, with_skill: bool, index: int, timeout: int) -> dict:
    task = TASKS[name]
    work = Path(tempfile.mkdtemp(prefix=f"roblox-eval-{name}-"))
    game = work / "game"
    game.mkdir()
    project.create_project(game, name)
    config = {"mcpServers": {"roblox": {
        "command": "uv",
        "args": ["run", "--project", str(ROOT), "roblox-mcp", "--project", str(game)],
        "env": {"ROBLOX_MCP_BIN_DIR": os.environ.get("ROBLOX_MCP_BIN_DIR", "")},
    }}}  # fmt: skip
    (work / "mcp.json").write_text(json.dumps(config))
    # the user's plugins (e.g. coding-style plugins) would confound both conditions
    user_settings = Path.home() / ".claude" / "settings.json"
    enabled = json.loads(user_settings.read_text()).get("enabledPlugins", {}) if (
        user_settings.is_file()) else {}  # fmt: skip
    (work / "settings.json").write_text(
        json.dumps({"enabledPlugins": dict.fromkeys(enabled, False)})
    )
    allowed = ["mcp__roblox__*", "Read", "Write", "Edit", "Glob", "Grep"]
    prompt = f"{task['prompt']}\n\nThe game's Rojo project is the current directory."
    # the prompt goes first: --allowedTools/--disallowedTools take several values
    args = ["claude", "-p", prompt, "--strict-mcp-config", "--mcp-config",
            str(work / "mcp.json"), "--settings", str(work / "settings.json"),
            "--output-format", "stream-json", "--verbose"]  # fmt: skip
    if with_skill:
        (game / ".claude/skills").mkdir(parents=True)
        (game / ".claude/skills/roblox-studio").symlink_to(SKILL)
        allowed.append("Skill")
    else:
        args += ["--disallowedTools", "mcp__roblox__read_guide"]
    args += ["--allowedTools", ",".join(allowed)]
    before = luau_files(game)
    started = datetime.datetime.now()
    try:
        out = subprocess.run(args, cwd=game, capture_output=True, text=True, timeout=timeout)
        events = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
    except subprocess.TimeoutExpired:
        events = [{"type": "result", "is_error": True, "result": "timeout"}]
    meta = next((e for e in events if e.get("type") == "result"), {})
    calls = [c for e in events if e.get("type") == "assistant"
             for c in e["message"]["content"] if c.get("type") == "tool_use"]  # fmt: skip
    # record which skill, not just that the Skill tool was called
    used = [f"Skill:{c['input'].get('skill')}" if c["name"] == "Skill" else c["name"]
            for c in calls]  # fmt: skip
    result = {
        "task": name,
        "skill": with_skill,
        "run": index,
        "seconds": int((datetime.datetime.now() - started).total_seconds()),
        "turns": meta.get("num_turns"),
        "cost_usd": meta.get("total_cost_usd"),
        "agent_error": meta.get("is_error", True),
        "used_skill": "Skill:roblox-studio" in used or "mcp__roblox__read_guide" in used,
        "tools": sorted(set(used)),
        "workdir": str(work),
        **grade(game, task),
    }
    if luau_files(game) == before:  # nothing written: not a pass, whatever the checks say
        result.update(all_pass=False, score="0 (no changes)")
    print(f"{name:5} skill={with_skill!s:5} #{index}: {result['score']}", file=sys.stderr)
    return result


def report(results: list[dict]) -> str:
    lines = ["| task | skill | read it | run | score | type errors | deprecated | failed checks |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for r in sorted(results, key=lambda r: (r["task"], not r["skill"], r["run"])):
        failed = [n for n, ok in r["checks"].items() if not ok]
        if r.get("tests_ok") is False:
            failed.append(f"tests ({r['tests']})")
        lines.append(f"| {r['task']} | {'with' if r['skill'] else 'without'} | "
                     f"{'yes' if r['used_skill'] else 'no'} | {r['run']} | "
                     f"{r['score']} | {r['type_errors']} | {', '.join(r['deprecated']) or '-'} | "
                     f"{', '.join(failed) or '-'} |")  # fmt: skip
    for skill in (True, False):
        rs = [r for r in results if r["skill"] == skill]
        ok = sum(r["all_pass"] for r in rs)
        lines.append(f"\n{'With' if skill else 'Without'} skill: {ok}/{len(rs)} runs pass "
                     "every check.")  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--tasks", default=",".join(TASKS))
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    jobs = [(t, s, i) for t in args.tasks.split(",") for s in (True, False)
            for i in range(1, args.runs + 1)]  # fmt: skip
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda j: run_one(*j, args.timeout), jobs))
    stamp = datetime.date.today().isoformat()
    out = ROOT / "evals" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stamp}.json").write_text(json.dumps(results, indent=2) + "\n")
    (out / f"{stamp}.md").write_text(report(results))
    print(report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
