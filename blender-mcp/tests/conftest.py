import threading
import time

import pytest
from blender_mcp_addon.listener import Listener, MainThreadQueue


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeBlender:
    """A Listener with stub handlers and a thread standing in for Blender's main thread."""

    def __init__(self, handlers, token=None):
        self.queue = MainThreadQueue()
        self.listener = Listener(
            handlers, self.queue, port=0, token=token, server_info={"blender_version": "fake"}
        )
        self._stop = threading.Event()
        self.main_thread = threading.Thread(target=self._drain_loop, name="fake-main")

    def _drain_loop(self):
        while not self._stop.is_set():
            self.queue.drain()
            time.sleep(0.002)

    def start(self):
        self.main_thread.start()
        self.listener.start()
        return self

    def stop(self):
        self.listener.stop()
        self._stop.set()
        self.main_thread.join()


@pytest.fixture
def fake_blender():
    started = []

    def make(handlers, token=None):
        fb = FakeBlender(handlers, token).start()
        started.append(fb)
        return fb

    yield make
    for fb in started:
        fb.stop()
