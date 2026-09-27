"""Load the add-on straight from this repo and start listening, without installing it.

    blender --python scripts/run_in_blender.py                        # GUI, for development
    blender --background --python scripts/run_in_blender.py -- --port 9877   # headless

In GUI mode the add-on registers normally (sidebar panel, timers). In --background
mode Blender has no event loop to fire timers, so this script drains the request
queue itself on the main thread until Ctrl+C.
"""

import argparse
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon"))

import blender_mcp_addon  # noqa: E402
from blender_mcp_addon import protocol, runtime  # noqa: E402


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="run_in_blender.py")
    parser.add_argument("--host", default=protocol.DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=protocol.DEFAULT_PORT)
    parser.add_argument("--token", default=None)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    if bpy.app.background:
        listener = runtime.start(args.host, args.port, args.token)
        # Parsed by tests/integration to find the port when --port 0 is used.
        print(f"BLENDER_MCP_READY {listener.host}:{listener.port}", flush=True)
        try:
            while True:
                runtime.main_thread.drain()
                time.sleep(runtime.DRAIN_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            runtime.stop()
    else:
        blender_mcp_addon.register()
        runtime.start(args.host, args.port, args.token)
        print(f"blender-mcp: {runtime.status()}", flush=True)


main()
