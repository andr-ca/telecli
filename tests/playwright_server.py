"""Shared uvicorn server helper for Playwright-backed test modules."""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from typing import Callable

import uvicorn


def reserve_free_port(host: str) -> int:
    """Allocate a free local TCP port for a temporary test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


class ManagedUvicornServer:
    """Start and stop a uvicorn server in a background thread for tests."""

    def __init__(
        self,
        app_path: str,
        host: str,
        port: int,
        *,
        configure: Callable[[], None] | None = None,
    ) -> None:
        self.app_path = app_path
        self.host = host
        self.port = port
        self.configure = configure
        self.thread: threading.Thread | None = None
        self.server: uvicorn.Server | None = None
        self.server_ready = False
        self.error: Exception | None = None

    def _run(self) -> None:
        try:
            if self.configure:
                self.configure()
            config = uvicorn.Config(
                self.app_path,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False,
            )
            self.server = uvicorn.Server(config)
            self.server_ready = True
            asyncio.run(self.server.serve())
        except Exception as exc:  # pragma: no cover - surfaced through startup failure
            self.error = exc
            self.server_ready = False

    def start(self) -> None:
        """Start the server thread and wait for the listening socket."""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        for _ in range(50):
            if self.error:
                raise RuntimeError(f"Server failed to start: {self.error}") from self.error
            if self.server_ready:
                time.sleep(0.5)
                break
            time.sleep(0.1)

        for _ in range(20):
            if self.error:
                raise RuntimeError(f"Server failed to start: {self.error}") from self.error
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    if sock.connect_ex((self.host, self.port)) == 0:
                        time.sleep(0.3)
                        return
            except OSError:
                pass
            time.sleep(0.1)

        raise RuntimeError(f"Timed out waiting for server on {self.host}:{self.port}")

    def stop(self) -> None:
        """Request shutdown and wait briefly for the server thread to exit."""
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive() and self.server:
                self.server.force_exit = True
                self.thread.join(timeout=5)
