"""Unit tests for the managed Playwright uvicorn test server helper."""

from tests.playwright_server import ManagedUvicornServer


class FakeThread:
    def __init__(self):
        self.join_calls = []
        self.alive = False

    def join(self, timeout=None):
        self.join_calls.append(timeout)

    def is_alive(self):
        return self.alive


class FakeServer:
    def __init__(self):
        self.should_exit = False
        self.force_exit = False


def test_managed_uvicorn_server_stop_requests_exit_and_joins_thread():
    """Stopping the helper should ask uvicorn to exit and then join the server thread."""
    managed = ManagedUvicornServer("src.web_app:app", "127.0.0.1", 9001)
    managed.server = FakeServer()
    managed.thread = FakeThread()

    managed.stop()

    assert managed.server.should_exit is True
    assert managed.thread.join_calls == [5]
