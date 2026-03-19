"""Tests for application entrypoint behavior."""

import asyncio

import pytest

from src import main as main_module


class FakeLogger:
    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class FakeSessionManager:
    def __init__(self):
        self.close_all_calls = 0

    async def close_all(self):
        self.close_all_calls += 1


class FakeUvicornConfig:
    def __init__(self, app, **kwargs):
        self.app = app
        self.kwargs = kwargs


class FakeUvicornServer:
    instances = []

    def __init__(self, config):
        self.config = config
        self.serve_calls = 0
        self.__class__.instances.append(self)

    async def serve(self):
        self.serve_calls += 1


def _install_main_fakes(monkeypatch):
    web_injections = []
    telegram_injections = []
    telegram_main_calls = []

    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "get_logger", lambda _name: FakeLogger())
    monkeypatch.setattr(main_module, "SessionManager", FakeSessionManager)
    monkeypatch.setattr(main_module.uvicorn, "Config", FakeUvicornConfig)
    monkeypatch.setattr(main_module.uvicorn, "Server", FakeUvicornServer)
    monkeypatch.setattr(
        main_module.web_app_module,
        "set_session_manager",
        lambda manager, managed=False: web_injections.append((manager, managed)),
    )
    monkeypatch.setattr(
        main_module.telegram_bot,
        "set_session_manager",
        lambda manager: telegram_injections.append(manager),
    )

    async def fake_telegram_main(shared_session_manager=None):
        telegram_main_calls.append(shared_session_manager)

    monkeypatch.setattr(main_module.telegram_bot, "main", fake_telegram_main)
    return web_injections, telegram_injections, telegram_main_calls


@pytest.mark.asyncio
async def test_main_skips_telegram_when_bot_token_is_missing(monkeypatch):
    """Web startup should still work when Telegram is not configured."""
    FakeUvicornServer.instances.clear()
    web_injections, telegram_injections, telegram_main_calls = _install_main_fakes(monkeypatch)

    monkeypatch.setattr(main_module.Config, "validate", lambda: None)
    monkeypatch.setattr(main_module.Config, "TELEGRAM_BOT_TOKEN", "")

    await main_module.main()

    assert len(FakeUvicornServer.instances) == 1
    assert FakeUvicornServer.instances[0].serve_calls == 1
    assert telegram_main_calls == []
    assert len(web_injections) == 2
    assert isinstance(web_injections[0][0], FakeSessionManager)
    assert web_injections[0][1] is False
    assert web_injections[1] == (None, False)
    assert len(telegram_injections) == 2
    assert isinstance(telegram_injections[0], FakeSessionManager)
    assert telegram_injections[1] is None


@pytest.mark.asyncio
async def test_main_starts_telegram_when_bot_token_is_configured(monkeypatch):
    """Telegram startup should still be included when a bot token exists."""
    FakeUvicornServer.instances.clear()
    _web_injections, _telegram_injections, telegram_main_calls = _install_main_fakes(monkeypatch)

    monkeypatch.setattr(main_module.Config, "validate", lambda: None)
    monkeypatch.setattr(main_module.Config, "TELEGRAM_BOT_TOKEN", "telegram-token")

    await main_module.main()

    assert len(FakeUvicornServer.instances) == 1
    assert FakeUvicornServer.instances[0].serve_calls == 1
    assert len(telegram_main_calls) == 1
    assert isinstance(telegram_main_calls[0], FakeSessionManager)


@pytest.mark.asyncio
async def test_main_cancels_telegram_when_web_server_fails(monkeypatch):
    """Telegram should not keep running if the web server exits during startup."""
    FakeUvicornServer.instances.clear()
    web_injections = []
    telegram_injections = []
    telegram_cancelled = asyncio.Event()

    class FailingServer(FakeUvicornServer):
        async def serve(self):
            self.serve_calls += 1
            raise SystemExit(1)

    async def blocking_telegram_main(shared_session_manager=None):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            telegram_cancelled.set()
            raise

    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "get_logger", lambda _name: FakeLogger())
    monkeypatch.setattr(main_module, "SessionManager", FakeSessionManager)
    monkeypatch.setattr(main_module.uvicorn, "Config", FakeUvicornConfig)
    monkeypatch.setattr(main_module.uvicorn, "Server", FailingServer)
    monkeypatch.setattr(
        main_module.web_app_module,
        "set_session_manager",
        lambda manager, managed=False: web_injections.append((manager, managed)),
    )
    monkeypatch.setattr(
        main_module.telegram_bot,
        "set_session_manager",
        lambda manager: telegram_injections.append(manager),
    )
    monkeypatch.setattr(main_module.telegram_bot, "main", blocking_telegram_main)
    monkeypatch.setattr(main_module.Config, "validate", lambda: None)
    monkeypatch.setattr(main_module.Config, "TELEGRAM_BOT_TOKEN", "telegram-token")

    await main_module.main()

    assert len(FailingServer.instances) == 1
    assert FailingServer.instances[0].serve_calls == 1
    assert telegram_cancelled.is_set()
    assert web_injections[-1] == (None, False)
    assert telegram_injections[-1] is None


@pytest.mark.asyncio
async def test_main_cancels_telegram_when_web_server_stops(monkeypatch):
    """Telegram should stop when the web server exits cleanly, such as after Ctrl+C."""
    FakeUvicornServer.instances.clear()
    web_injections = []
    telegram_injections = []
    telegram_cancelled = asyncio.Event()

    class ReturningServer(FakeUvicornServer):
        async def serve(self):
            self.serve_calls += 1
            return None

    async def blocking_telegram_main(shared_session_manager=None):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            telegram_cancelled.set()
            raise

    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "get_logger", lambda _name: FakeLogger())
    monkeypatch.setattr(main_module, "SessionManager", FakeSessionManager)
    monkeypatch.setattr(main_module.uvicorn, "Config", FakeUvicornConfig)
    monkeypatch.setattr(main_module.uvicorn, "Server", ReturningServer)
    monkeypatch.setattr(
        main_module.web_app_module,
        "set_session_manager",
        lambda manager, managed=False: web_injections.append((manager, managed)),
    )
    monkeypatch.setattr(
        main_module.telegram_bot,
        "set_session_manager",
        lambda manager: telegram_injections.append(manager),
    )
    monkeypatch.setattr(main_module.telegram_bot, "main", blocking_telegram_main)
    monkeypatch.setattr(main_module.Config, "validate", lambda: None)
    monkeypatch.setattr(main_module.Config, "TELEGRAM_BOT_TOKEN", "telegram-token")

    await main_module.main()

    assert len(ReturningServer.instances) == 1
    assert ReturningServer.instances[0].serve_calls == 1
    assert telegram_cancelled.is_set()
    assert web_injections[-1] == (None, False)
    assert telegram_injections[-1] is None
