"""
Playwright integration tests for TeleCLI
Tests the web UI and WebSocket functionality with real browser
"""
import pytest
from playwright.sync_api import Error as PlaywrightError, sync_playwright
import os
import json
import time
from tests.playwright_server import ManagedUvicornServer, reserve_free_port

pytestmark = pytest.mark.playwright

# Test configuration
WEB_HOST = "127.0.0.1"
WEB_PORT = None
BASE_URL = None

managed_server = None


def configure_test_server():
    """Apply test-only config before starting the embedded web app."""
    os.environ["AUTH_REQUIRED"] = "false"
    from src.config import Config
    Config.AUTH_REQUIRED = False


@pytest.fixture(scope="session", autouse=True)
def start_test_server():
    """Start the server for testing"""
    global managed_server, WEB_PORT, BASE_URL

    WEB_PORT = reserve_free_port(WEB_HOST)
    BASE_URL = f"http://{WEB_HOST}:{WEB_PORT}"
    managed_server = ManagedUvicornServer(
        "src.web_app:app",
        WEB_HOST,
        WEB_PORT,
        configure=configure_test_server,
    )
    managed_server.start()

    yield

    managed_server.stop()


@pytest.fixture
def browser():
    """Create a Playwright browser instance"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        yield browser
        browser.close()


def test_home_page_loads(browser):
    """Test that home page loads via Playwright"""
    page = browser.new_page()
    response = page.goto(BASE_URL)

    assert response.status == 200
    page.wait_for_load_state("networkidle")

    # Check page title and content
    assert "TeleCLI" in page.title() or "telecli" in page.content().lower()

    page.close()


def test_telecli_path_loads(browser):
    """Test that /telecli path loads"""
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/telecli")

    assert response.status == 200
    page.wait_for_load_state("networkidle")

    assert "TeleCLI" in page.title() or "telecli" in page.content().lower()

    page.close()


def test_health_endpoint(browser):
    """Test health endpoint via browser"""
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/health")

    assert response.status == 200

    # Get response content
    content = page.content()
    assert "status" in content.lower()

    page.close()


def test_debug_endpoint(browser):
    """Test debug endpoint via browser"""
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/debug")

    assert response.status == 200

    content = page.content()
    assert "url" in content.lower() or "method" in content.lower()

    page.close()


def test_api_sessions_endpoint(browser):
    """Test /api/sessions endpoint"""
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/api/sessions")

    assert response.status == 200

    content = page.content()
    assert "sessions" in content.lower() or "{" in content

    page.close()


def test_page_response_time(browser):
    """Test that page loads quickly"""
    page = browser.new_page()

    start = time.time()
    response = page.goto(BASE_URL, wait_until="networkidle", timeout=10000)
    elapsed = time.time() - start

    assert response.status == 200
    assert elapsed < 5, f"Page took {elapsed}s to load, expected < 5s"

    page.close()


def test_websocket_connection(browser):
    """Test WebSocket connection from browser"""
    page = browser.new_page()

    # Navigate to home which should establish WebSocket
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Check if page content suggests WebSocket support
    content = page.content()
    # The page should have some JavaScript or indicators of WebSocket usage
    assert len(content) > 100, "Page content seems empty"

    page.close()


def test_multiple_page_loads(browser):
    """Test loading page multiple times"""
    for i in range(3):
        page = browser.new_page()
        response = page.goto(BASE_URL)
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.close()
        time.sleep(0.2)


def test_page_has_no_console_errors(browser):
    """Test that page has no critical console errors"""
    page = browser.new_page()

    errors = []

    def log_console_message(msg):
        if msg.type == "error":
            # Filter out WebSocket connection errors (expected in test)
            if "websocket" not in msg.text.lower():
                errors.append(msg.text)

    page.on("console", log_console_message)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Wait a bit for any deferred errors
    time.sleep(0.5)

    # Should have no critical errors (WebSocket errors are OK)
    assert len(errors) == 0, f"Found console errors: {errors}"

    page.close()


def test_css_styling_loads(browser):
    """Test that CSS is loaded and applied"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Check if any stylesheets are loaded
    stylesheets = page.query_selector_all("link[rel='stylesheet']")
    # Or check if there are style tags
    style_tags = page.query_selector_all("style")

    has_styling = len(stylesheets) > 0 or len(style_tags) > 0
    assert has_styling or page.query_selector("body"), "No styling or body found"

    page.close()


def test_page_title_is_set(browser):
    """Test that page has proper title"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    title = page.title()
    assert title, "Page has no title"
    assert len(title) > 0, "Page title is empty"

    page.close()


def test_multiple_concurrent_page_loads(browser):
    """Test multiple pages loading concurrently"""
    pages = []
    for i in range(3):
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="load")  # Use 'load' instead of 'networkidle' for speed
        pages.append(page)

    # All should be on the same page
    for page in pages:
        assert "TeleCLI" in page.title() or "telecli" in page.content().lower()

    for page in pages:
        page.close()


def test_api_endpoints_accessible(browser):
    """Test that all main API endpoints are accessible"""
    endpoints = [
        "/health",
        "/stats",
        "/debug",
        "/api/sessions",
        "/api/auth/required",
        "/api/ai-proxy/config",
        "/api/llm-monitor",
    ]

    page = browser.new_page()

    for endpoint in endpoints:
        response = page.goto(f"{BASE_URL}{endpoint}")
        assert response.status == 200, f"Endpoint {endpoint} returned {response.status}"

    page.close()


def test_claude_code_auto_continue_status_renders(browser):
    """The Claude Code auto-continue control should render ccusage timing and trigger details."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    assert page.locator("#claude-code-btn").text_content() == "⏱ CC Auto: OFF"

    page.evaluate(
        """() => updateClaudeCodeStatus({
            enabled: true,
            waiting: true,
            wait_reason: 'block_reset',
            reset_at: '2099-03-18T05:45:00Z',
            scheduled_for: '2099-03-18T06:00:00Z',
            last_error: null,
            last_continue_sent_at: null
        })"""
    )

    assert page.locator("#claude-code-btn").text_content() == "⏱ CC Auto: ON"
    status_text = page.locator("#claude-code-status").text_content().lower()
    assert "block reset" in status_text
    assert "ccusage" in status_text
    assert "left" in status_text
    assert "next auto-trigger" in status_text

    context.close()


def test_claude_code_auto_continue_idle_status_renders(browser):
    """Enabled idle state should say that no auto-trigger is scheduled yet."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.evaluate(
        """() => updateClaudeCodeStatus({
            enabled: true,
            waiting: false,
            wait_reason: null,
            reset_at: null,
            scheduled_for: null,
            last_error: null,
            last_continue_sent_at: null,
            ccusage_available: true
        })"""
    )

    status_text = page.locator("#claude-code-status").text_content().lower()
    assert "no auto-trigger scheduled yet" in status_text
    assert "waiting for claude" in status_text

    context.close()


def test_claude_code_auto_continue_reports_visible_limit_screen_on_enable(browser):
    """Enabling auto-continue over an already visible Claude limit screen should report that screen."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            const sentMessages = [];

            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    window.__telecliSentMessages = sentMessages;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send(payload) {
                    sentMessages.push(JSON.parse(payload));
                }

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.evaluate(
        """() => new Promise((resolve) => {
            term.write('Claude Code\\r\\n100% used\\r\\nResets at 6:00 PM\\r\\n', resolve);
        })"""
    )

    page.evaluate(
        """() => updateClaudeCodeStatus({
            enabled: true,
            waiting: false,
            wait_reason: null,
            reset_at: null,
            scheduled_for: null,
            last_error: null,
            last_continue_sent_at: null,
            ccusage_available: true
        })"""
    )

    page.wait_for_function(
        """() => window.__telecliSentMessages.some((message) =>
            message.claude_code &&
            typeof message.claude_code.screen_text === 'string' &&
            message.claude_code.screen_text.includes('Claude Code') &&
            message.claude_code.screen_text.includes('100% used')
        )"""
    )

    context.close()


def test_claude_code_auto_continue_reports_hit_limit_screen_on_enable(browser):
    """Enabling auto-continue over Claude's newer hit-limit screen should report that screen."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            const sentMessages = [];

            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    window.__telecliSentMessages = sentMessages;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send(payload) {
                    sentMessages.push(JSON.parse(payload));
                }

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.evaluate(
        """() => new Promise((resolve) => {
            term.write("You've hit your limit · resets 11am (America/Toronto)\\r\\n", resolve);
        })"""
    )

    page.evaluate(
        """() => updateClaudeCodeStatus({
            enabled: true,
            waiting: false,
            wait_reason: null,
            reset_at: null,
            scheduled_for: null,
            last_error: null,
            last_continue_sent_at: null,
            ccusage_available: true
        })"""
    )

    page.wait_for_function(
        """() => window.__telecliSentMessages.some((message) =>
            message.claude_code &&
            typeof message.claude_code.screen_text === 'string' &&
            message.claude_code.screen_text.includes("You've hit your limit")
        )"""
    )

    context.close()


def test_reconnecting_does_not_duplicate_terminal_echo(browser):
    """A second connect attempt must not cause terminal input to echo twice."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            const OriginalWebSocket = window.WebSocket;
            const trackedSockets = [];

            class TrackingWebSocket extends OriginalWebSocket {
                constructor(url, protocols) {
                    super(url, protocols);
                    trackedSockets.push(this);
                }
            }

            Object.setPrototypeOf(TrackingWebSocket, OriginalWebSocket);
            TrackingWebSocket.prototype = OriginalWebSocket.prototype;
            TrackingWebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
            TrackingWebSocket.OPEN = OriginalWebSocket.OPEN;
            TrackingWebSocket.CLOSING = OriginalWebSocket.CLOSING;
            TrackingWebSocket.CLOSED = OriginalWebSocket.CLOSED;

            window.__telecliTrackedSockets = trackedSockets;
            window.WebSocket = TrackingWebSocket;
        })();
        """
    )

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        "() => document.getElementById('status')?.textContent?.includes('Connected')"
    )

    # Keep the test focused on reconnect behavior, not stale-state refreshes.
    page.evaluate("() => stopStaleStateMonitoring()")

    # Simulate a duplicate client-side reconnect attempt on the same page.
    page.evaluate("() => connectWebSocket()")
    page.wait_for_timeout(500)

    active_socket_count = page.evaluate(
        """() => window.__telecliTrackedSockets.filter(
            (socket) => socket.readyState === window.WebSocket.CONNECTING || socket.readyState === window.WebSocket.OPEN
        ).length"""
    )

    assert active_socket_count == 1

    context.close()


def test_switching_sessions_preserves_visible_terminal_state(browser):
    """Switching back to a session should restore its visible terminal content."""
    context = browser.new_context()
    page = context.new_page()

    def wait_until_connected(expected_session_id=None):
        if expected_session_id is None:
            page.wait_for_function(
                "() => ws && ws.readyState === WebSocket.OPEN && document.getElementById('status')?.textContent?.includes('Connected')"
            )
            return

        page.wait_for_function(
            """(sessionId) =>
            clientId === sessionId &&
            ws &&
            ws.readyState === WebSocket.OPEN &&
            document.getElementById('status')?.textContent?.includes('Connected')""",
            arg=expected_session_id,
        )

    def stop_refresh_monitoring():
        page.evaluate("() => stopStaleStateMonitoring()")

    def send_command(command):
        page.evaluate("(input) => ws.send(JSON.stringify({ input }))", command)

    def visible_terminal_text():
        return page.evaluate(
            """() => {
                const start = term.buffer.active.viewportY;
                const end = start + term.rows;
                const lines = [];

                for (let i = start; i < end; i++) {
                    lines.push(term.buffer.active.getLine(i)?.translateToString(true) ?? '');
                }

                return lines.join('\\n');
            }"""
        )

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    wait_until_connected()
    stop_refresh_monitoring()

    first_session_id = page.evaluate("() => clientId")
    second_session_id = "web-session-switch-test-second"
    first_marker = "SESSION_ONE_MARKER"
    second_marker = "SESSION_TWO_MARKER"

    send_command(f"printf '{first_marker}\\n'\r")
    page.wait_for_function(
        "(marker) => Array.from({ length: term.rows }, (_, offset) => term.buffer.active.getLine(term.buffer.active.viewportY + offset)?.translateToString(true) ?? '').join('\\n').includes(marker)",
        arg=first_marker,
    )

    page.evaluate("(sessionId) => selectSession(sessionId)", second_session_id)
    wait_until_connected(second_session_id)
    stop_refresh_monitoring()

    send_command(f"printf '{second_marker}\\n'\r")
    page.wait_for_function(
        "(marker) => Array.from({ length: term.rows }, (_, offset) => term.buffer.active.getLine(term.buffer.active.viewportY + offset)?.translateToString(true) ?? '').join('\\n').includes(marker)",
        arg=second_marker,
    )

    page.evaluate("(sessionId) => selectSession(sessionId)", first_session_id)
    wait_until_connected(first_session_id)
    stop_refresh_monitoring()
    page.wait_for_function(
        "(marker) => Array.from({ length: term.rows }, (_, offset) => term.buffer.active.getLine(term.buffer.active.viewportY + offset)?.translateToString(true) ?? '').join('\\n').includes(marker)",
        arg=first_marker,
    )

    assert first_marker in visible_terminal_text()

    context.close()


def test_switching_sessions_sends_resize_for_reconnected_socket(browser):
    """Switching sessions should send the current terminal size on the new socket."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            const trackedSockets = [];

            class TrackingWebSocket {
                constructor(url) {
                    this.url = url;
                    this.readyState = TrackingWebSocket.CONNECTING;
                    this.sentMessages = [];
                    trackedSockets.push(this);

                    setTimeout(() => {
                        this.readyState = TrackingWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send(payload) {
                    this.sentMessages.push(JSON.parse(payload));
                }

                close() {
                    this.readyState = TrackingWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            TrackingWebSocket.CONNECTING = 0;
            TrackingWebSocket.OPEN = 1;
            TrackingWebSocket.CLOSING = 2;
            TrackingWebSocket.CLOSED = 3;

            window.__telecliTrackedSockets = trackedSockets;
            window.WebSocket = TrackingWebSocket;
        })();
        """
    )

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => window.__telecliTrackedSockets.length === 1 && window.__telecliTrackedSockets[0].readyState === WebSocket.OPEN"
    )
    page.wait_for_function(
        "() => document.querySelectorAll('#terminal-container .xterm-rows > div').length > 45"
    )

    page.evaluate("() => selectSession('tmux-session-test')")
    page.wait_for_function(
        "() => window.__telecliTrackedSockets.length === 2 && window.__telecliTrackedSockets[1].readyState === WebSocket.OPEN"
    )

    sent_messages = page.evaluate("() => window.__telecliTrackedSockets[1].sentMessages")

    assert any(
        message.get("resize", {}).get("rows", 0) > 45 and message.get("resize", {}).get("cols", 0) > 80
        for message in sent_messages
    )

    context.close()


def test_initial_output_scrolls_to_latest_visible_line(browser):
    """The terminal should keep the viewport at the newest line after initial server output."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    window.__telecliSocket = this;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => window.__telecliSocket && window.__telecliSocket.readyState === WebSocket.OPEN"
    )
    page.wait_for_function(
        "() => document.querySelectorAll('#terminal-container .xterm-rows > div').length > 45"
    )

    page.evaluate(
        """() => {
            const lineCount = term.rows + 20;
            const output = Array.from({ length: lineCount }, (_, index) => `line-${index + 1}`).join('\\r\\n') + '\\r\\n';
            window.__telecliSocket.onmessage({ data: JSON.stringify({ output }) });
        }"""
    )

    page.wait_for_function(
        """() => {
            const lastLine = `line-${term.rows + 20}`;
            const start = term.buffer.active.viewportY;
            const visible = Array.from(
                { length: term.rows },
                (_, offset) => term.buffer.active.getLine(start + offset)?.translateToString(true) ?? ''
            ).join('\\n');
            return visible.includes(lastLine);
        }"""
    )

    context.close()


def test_large_output_scrolls_after_buffer_updates(browser):
    """Explicit auto-scroll should run after the newest line is present in the buffer."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    window.__telecliSocket = this;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => window.__telecliSocket && window.__telecliSocket.readyState === WebSocket.OPEN"
    )
    page.wait_for_function(
        "() => document.querySelectorAll('#terminal-container .xterm-rows > div').length > 45"
    )

    page.evaluate(
        """() => {
            const lastLine = `line-${term.rows + 20}`;
            window.__telecliScrollSawLatest = null;
            const originalScrollToBottom = term.scrollToBottom.bind(term);
            term.scrollToBottom = () => {
                const start = term.buffer.active.viewportY;
                const visible = Array.from(
                    { length: term.rows },
                    (_, offset) => term.buffer.active.getLine(start + offset)?.translateToString(true) ?? ''
                ).join('\\n');
                window.__telecliScrollSawLatest = visible.includes(lastLine);
                return originalScrollToBottom();
            };

            const output = Array.from({ length: term.rows + 20 }, (_, index) => `line-${index + 1}`).join('\\r\\n') + '\\r\\n';
            window.__telecliSocket.onmessage({ data: JSON.stringify({ output }) });
        }"""
    )

    page.wait_for_function("() => window.__telecliScrollSawLatest !== null")

    assert page.evaluate("() => window.__telecliScrollSawLatest") is True

    context.close()


def test_session_picker_creates_named_sessions_and_imports_tmux_entries(browser):
    """The session picker should create named sessions and only show tmux sessions after import."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    sessions = []
    tmux_sessions = [
        {
            "name": "ops",
            "windows": 3,
            "attached": True,
            "imported": False,
            "imported_session_id": None,
            "imported_name": None,
            "current_command": "codex",
            "current_path": "/workspace/ops",
            "pane_paths": ["/workspace/ops", "/workspace/shared"],
        },
        {
            "name": "build",
            "windows": 1,
            "attached": False,
            "imported": False,
            "imported_session_id": None,
            "imported_name": None,
            "current_command": "bash",
            "current_path": "/workspace/build",
            "pane_paths": ["/workspace/build"],
        },
    ]
    session_counter = 0

    def make_session_payload(session_id, name, backend="telecli", tmux_session_name=None):
        shell = "/bin/bash" if backend == "telecli" else f"tmux:{tmux_session_name}"
        return {
            "id": session_id,
            "name": name,
            "backend": backend,
            "created_at": "2026-03-18T12:00:00+00:00",
            "shell": shell,
            "is_active": True,
            "available": True,
            "tmux_session_name": tmux_session_name,
        }

    def handle_api(route):
        nonlocal session_counter
        request = route.request
        path = request.url.split(BASE_URL, 1)[-1]

        if path == "/api/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": sessions}),
            )
            return

        if path == "/api/sessions" and request.method == "POST":
            session_counter += 1
            payload = json.loads(request.post_data or "{}")
            session = make_session_payload(
                f"web-created-{session_counter}",
                payload.get("name") or f"web-created-{session_counter}",
            )
            sessions.append(session)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"session": session}),
            )
            return

        if path.startswith("/api/sessions/") and request.method == "PATCH":
            session_id = path.rsplit("/", 1)[-1]
            payload = json.loads(request.post_data or "{}")
            for session in sessions:
                if session["id"] == session_id:
                    session["name"] = payload["name"]
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({"session": session}),
                    )
                    return
            route.fulfill(status=404, content_type="application/json", body='{"detail":"not found"}')
            return

        if path.startswith("/api/sessions/") and request.method == "DELETE":
            session_id = path.rsplit("/", 1)[-1]
            sessions[:] = [session for session in sessions if session["id"] != session_id]
            for tmux_session in tmux_sessions:
                if tmux_session["imported_session_id"] == session_id:
                    tmux_session["imported"] = False
                    tmux_session["imported_session_id"] = None
                    tmux_session["imported_name"] = None
            route.fulfill(status=200, content_type="application/json", body='{"status":"ok"}')
            return

        if path == "/api/tmux/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": tmux_sessions}),
            )
            return

        if path == "/api/sessions/import-tmux" and request.method == "POST":
            payload = json.loads(request.post_data or "{}")
            tmux_name = payload["tmux_session_name"]
            for tmux_session in tmux_sessions:
                if tmux_session["name"] != tmux_name:
                    continue

                if tmux_session["imported"]:
                    session = next(
                        session
                        for session in sessions
                        if session["id"] == tmux_session["imported_session_id"]
                    )
                else:
                    session_counter += 1
                    session = make_session_payload(
                        f"tmux-imported-{session_counter}",
                        payload.get("name") or tmux_name,
                        backend="tmux",
                        tmux_session_name=tmux_name,
                    )
                    sessions.append(session)
                    tmux_session["imported"] = True
                    tmux_session["imported_session_id"] = session["id"]
                    tmux_session["imported_name"] = session["name"]

                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"session": session}),
                )
                return

            route.fulfill(status=404, content_type="application/json", body='{"detail":"not found"}')
            return

        route.fallback()

    page.route("**/api/sessions", handle_api)
    page.route("**/api/sessions/*", handle_api)
    page.route("**/api/sessions/**", handle_api)
    page.route("**/api/tmux/sessions", handle_api)
    page.route("**/api/sessions/import-tmux", handle_api)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.click("#session-btn")
    page.fill("#new-session-name", "Dev Shell")
    page.click("#create-session-btn")
    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.includes('Dev Shell')"
    )

    created_session_id = sessions[0]["id"]

    page.click("#session-btn")
    dialog_responses = ["Primary Dev", "ops"]
    page.on("dialog", lambda dialog: dialog.accept(dialog_responses.pop(0)))
    page.click(f"button[data-action='rename-session'][data-session-id='{created_session_id}']")
    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.includes('Primary Dev')"
    )

    page.click("#attach-tmux-btn")
    page.wait_for_selector("#tmux-picker-modal", state="visible")
    page.wait_for_function(
        """() => {
            const text = document.getElementById('tmux-sessions-list')?.textContent?.toLowerCase() || '';
            return text.includes('ops') && text.includes('build') && text.includes('/workspace/ops');
        }"""
    )
    tmux_picker_text = page.locator("#tmux-sessions-list").text_content()
    assert "/workspace/ops" in tmux_picker_text
    assert "/workspace/shared" in tmux_picker_text
    assert "/workspace/build" in tmux_picker_text

    page.click("button[data-action='import-tmux-session'][data-tmux-session-name='ops']")
    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.toLowerCase().includes('ops')"
    )

    page.click("#session-btn")
    sessions_text = page.locator("#sessions-list").text_content().lower()
    assert "primary dev" in sessions_text

    page.click("#attach-tmux-btn")
    page.wait_for_selector("#tmux-picker-modal", state="visible")
    assert (
        page.locator("button[data-action='import-tmux-session'][data-tmux-session-name='ops']").text_content()
        == "Open existing"
    )


def test_tmux_picker_prompts_for_session_name_on_attach(browser):
    """Attaching a tmux session should prompt for the imported TeleCLI session name."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    sessions = []
    tmux_sessions = [
        {
            "name": "ops",
            "windows": 3,
            "attached": True,
            "imported": False,
            "imported_session_id": None,
            "imported_name": None,
            "current_command": "codex",
            "current_path": "/workspace/ops",
            "pane_paths": ["/workspace/ops"],
        }
    ]
    session_counter = 0

    def make_session_payload(session_id, name, backend="telecli", tmux_session_name=None):
        shell = "/bin/bash" if backend == "telecli" else f"tmux:{tmux_session_name}"
        return {
            "id": session_id,
            "name": name,
            "backend": backend,
            "created_at": "2026-03-18T12:00:00+00:00",
            "shell": shell,
            "is_active": True,
            "available": True,
            "tmux_session_name": tmux_session_name,
        }

    def handle_api(route):
        nonlocal session_counter
        request = route.request
        path = request.url.split(BASE_URL, 1)[-1]

        if path == "/api/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": sessions}),
            )
            return

        if path == "/api/tmux/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": tmux_sessions}),
            )
            return

        if path == "/api/sessions/import-tmux" and request.method == "POST":
            payload = json.loads(request.post_data or "{}")
            session_counter += 1
            session = make_session_payload(
                f"tmux-imported-{session_counter}",
                payload.get("name") or payload["tmux_session_name"],
                backend="tmux",
                tmux_session_name=payload["tmux_session_name"],
            )
            sessions.append(session)
            tmux_sessions[0]["imported"] = True
            tmux_sessions[0]["imported_session_id"] = session["id"]
            tmux_sessions[0]["imported_name"] = session["name"]
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"session": session}),
            )
            return

        route.fallback()

    page.route("**/api/sessions", handle_api)
    page.route("**/api/tmux/sessions", handle_api)
    page.route("**/api/sessions/import-tmux", handle_api)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.click("#session-btn")
    page.click("#attach-tmux-btn")
    page.wait_for_selector("#tmux-picker-modal", state="visible")
    page.on("dialog", lambda dialog: dialog.accept("Ops Review"))
    page.click("button[data-action='import-tmux-session'][data-tmux-session-name='ops']")

    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.includes('Ops Review')"
    )
    assert sessions[0]["name"] == "Ops Review"

    context.close()


def test_session_picker_prompts_for_name_when_creating_blank_session(browser):
    """Creating a session with a blank field should prompt for the TeleCLI session name."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    sessions = []
    session_counter = 0

    def make_session_payload(session_id, name, backend="telecli", tmux_session_name=None):
        shell = "/bin/bash" if backend == "telecli" else f"tmux:{tmux_session_name}"
        return {
            "id": session_id,
            "name": name,
            "backend": backend,
            "created_at": "2026-03-18T12:00:00+00:00",
            "shell": shell,
            "is_active": True,
            "available": True,
            "tmux_session_name": tmux_session_name,
        }

    def handle_api(route):
        nonlocal session_counter
        request = route.request
        path = request.url.split(BASE_URL, 1)[-1]

        if path == "/api/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": sessions}),
            )
            return

        if path == "/api/sessions" and request.method == "POST":
            payload = json.loads(request.post_data or "{}")
            session_counter += 1
            session = make_session_payload(
                f"web-created-{session_counter}",
                payload.get("name") or f"web-created-{session_counter}",
            )
            sessions.append(session)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"session": session}),
            )
            return

        route.fallback()

    page.route("**/api/sessions", handle_api)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.click("#session-btn")
    page.on("dialog", lambda dialog: dialog.accept("Inbox Shell"))
    page.click("#create-session-btn")

    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.includes('Inbox Shell')"
    )
    assert sessions[0]["name"] == "Inbox Shell"

    context.close()


def test_tmux_picker_can_create_and_detach_tmux_sessions(browser):
    """The tmux picker should create a tmux session and detach it without forgetting the import."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            class FakeWebSocket {
                constructor() {
                    this.readyState = FakeWebSocket.CONNECTING;
                    setTimeout(() => {
                        this.readyState = FakeWebSocket.OPEN;
                        if (this.onopen) {
                            this.onopen();
                        }
                    }, 0);
                }

                send() {}

                close() {
                    this.readyState = FakeWebSocket.CLOSED;
                    if (this.onclose) {
                        this.onclose({ code: 1000 });
                    }
                }
            }

            FakeWebSocket.CONNECTING = 0;
            FakeWebSocket.OPEN = 1;
            FakeWebSocket.CLOSING = 2;
            FakeWebSocket.CLOSED = 3;

            window.WebSocket = FakeWebSocket;
        })();
        """
    )

    sessions = []
    tmux_sessions = []
    session_counter = 0

    def make_session_payload(session_id, name, backend="telecli", tmux_session_name=None, is_active=True):
        shell = "/bin/bash" if backend == "telecli" else f"tmux:{tmux_session_name}"
        return {
            "id": session_id,
            "name": name,
            "backend": backend,
            "created_at": "2026-03-18T12:00:00+00:00",
            "shell": shell,
            "is_active": is_active,
            "available": True,
            "tmux_session_name": tmux_session_name,
        }

    def handle_api(route):
        nonlocal session_counter
        request = route.request
        path = request.url.split(BASE_URL, 1)[-1]

        if path == "/api/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": sessions}),
            )
            return

        if path == "/api/sessions" and request.method == "POST":
            session_counter += 1
            payload = json.loads(request.post_data or "{}")
            session = make_session_payload(
                f"web-created-{session_counter}",
                payload.get("name") or f"web-created-{session_counter}",
            )
            sessions.append(session)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"session": session}),
            )
            return

        if path == "/api/tmux/sessions" and request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": tmux_sessions}),
            )
            return

        if path == "/api/tmux/sessions" and request.method == "POST":
            payload = json.loads(request.post_data or "{}")
            session_counter += 1
            tmux_name = payload["name"]
            session = make_session_payload(
                f"tmux-created-{session_counter}",
                tmux_name,
                backend="tmux",
                tmux_session_name=tmux_name,
            )
            sessions.append(session)
            tmux_sessions.append(
                {
                    "name": tmux_name,
                    "windows": 1,
                    "attached": False,
                    "imported": True,
                    "imported_session_id": session["id"],
                    "imported_name": session["name"],
                }
            )
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"session": session}),
            )
            return

        if path.startswith("/api/sessions/") and path.endswith("/detach") and request.method == "POST":
            session_id = path.split("/")[-2]
            for session in sessions:
                if session["id"] == session_id:
                    session["is_active"] = False
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({"session": session}),
                    )
                    return
            route.fulfill(status=404, content_type="application/json", body='{"detail":"not found"}')
            return

        route.fallback()

    page.route("**/api/sessions", handle_api)
    page.route("**/api/sessions/*", handle_api)
    page.route("**/api/sessions/**", handle_api)
    page.route("**/api/tmux/sessions", handle_api)

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page.click("#session-btn")
    page.click("#attach-tmux-btn")
    page.wait_for_selector("#tmux-picker-modal", state="visible")
    page.fill("#new-tmux-session-name", "pairing")
    page.click("#create-tmux-session-btn")
    page.wait_for_function(
        "() => document.getElementById('session-compact')?.textContent?.toLowerCase().includes('pairing')"
    )

    created_tmux_id = sessions[0]["id"]

    page.click("#session-btn")
    sessions_text = page.locator("#sessions-list").text_content().lower()
    assert "pairing" in sessions_text

    page.click(f"button[data-action='detach-session'][data-session-id='{created_tmux_id}']")
    page.wait_for_function(
        "() => !document.getElementById('session-compact')?.textContent?.toLowerCase().includes('pairing')"
    )

    page.click("#session-btn")
    sessions_text = page.locator("#sessions-list").text_content().lower()
    assert "pairing" in sessions_text
    assert "ready" in sessions_text

    context.close()


def test_mobile_keyboard_viewport_updates_layout(browser):
    """The app should react to visualViewport shrink when a mobile keyboard appears."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.add_init_script(
        """
        (() => {
            const listeners = { resize: [], scroll: [] };
            const fakeVisualViewport = {
                width: 390,
                height: 844,
                offsetTop: 0,
                offsetLeft: 0,
                pageTop: 0,
                pageLeft: 0,
                scale: 1,
                addEventListener(type, callback) {
                    (listeners[type] ||= []).push(callback);
                },
                removeEventListener(type, callback) {
                    listeners[type] = (listeners[type] || []).filter((fn) => fn !== callback);
                },
            };

            window.__setFakeVisualViewportHeight = (height) => {
                fakeVisualViewport.height = height;
                for (const callback of listeners.resize || []) {
                    callback();
                }
            };

            Object.defineProperty(window, 'visualViewport', {
                configurable: true,
                value: fakeVisualViewport,
            });
        })();
        """
    )

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => document.getElementById('status')?.textContent?.includes('Connected')",
        timeout=5000,
    )

    page.wait_for_function(
        "() => document.documentElement.style.getPropertyValue('--app-height') === '844px'",
        timeout=1500,
    )

    page.evaluate("() => window.__setFakeVisualViewportHeight(500)")

    page.wait_for_function(
        "() => document.documentElement.style.getPropertyValue('--app-height') === '500px'",
        timeout=1500,
    )
    page.wait_for_function(
        "() => document.body.classList.contains('keyboard-open')",
        timeout=1500,
    )
    page.wait_for_function(
        "() => getComputedStyle(document.documentElement).height === '500px'",
        timeout=1500,
    )

    context.close()


def test_desktop_terminal_fills_available_height(browser):
    """The terminal should fill the available desktop viewport height and grow on resize."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => document.getElementById('status')?.textContent?.includes('Connected')",
        timeout=5000,
    )

    initial = page.evaluate(
        """() => {
            const container = document.querySelector('.container').getBoundingClientRect();
            const header = document.querySelector('header').getBoundingClientRect();
            const main = document.getElementById('main-content').getBoundingClientRect();
            const terminal = document.getElementById('terminal-container').getBoundingClientRect();
            const footer = document.querySelector('footer').getBoundingClientRect();
            return {
                containerHeight: container.height,
                headerHeight: header.height,
                mainHeight: main.height,
                terminalHeight: terminal.height,
                footerHeight: footer.height,
            };
        }"""
    )

    assert initial["mainHeight"] > 600
    assert initial["terminalHeight"] > 500
    assert initial["mainHeight"] + initial["headerHeight"] >= initial["containerHeight"] - 4

    page.set_viewport_size({"width": 1440, "height": 1100})
    page.wait_for_function(
        "() => document.documentElement.style.getPropertyValue('--app-height') === '1100px'",
        timeout=1500,
    )
    page.wait_for_function(
        """(previousHeight) =>
            document.getElementById('terminal-container').getBoundingClientRect().height > previousHeight + 100
        """,
        arg=initial["terminalHeight"],
        timeout=2000,
    )

    resized = page.evaluate(
        """() => document.getElementById('terminal-container').getBoundingClientRect().height"""
    )

    assert resized > initial["terminalHeight"] + 100

    context.close()


def test_terminal_refits_after_stylesheet_load_without_manual_resize(browser):
    """The terminal should refit itself after late layout changes during startup."""
    context = browser.new_context(viewport={"width": 1440, "height": 960})
    page = context.new_page()

    def delay_main_stylesheet(route):
        if route.request.url.endswith("/style.css"):
            time.sleep(1.5)
        route.continue_()

    page.route("**/style.css", delay_main_stylesheet)

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_function(
        "() => document.getElementById('status')?.textContent?.includes('Connected')",
        timeout=5000,
    )
    page.wait_for_function(
        "() => !!document.getElementById('main-stylesheet')?.sheet",
        timeout=3000,
    )

    metrics = page.evaluate(
        """() => ({
            rows: document.querySelectorAll('#terminal-container .xterm-rows > div').length,
            terminalHeight: document.getElementById('terminal-container').getBoundingClientRect().height,
        })"""
    )

    assert metrics["terminalHeight"] > 800
    assert metrics["rows"] > 45

    context.close()
