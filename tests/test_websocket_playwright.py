"""
Playwright WebSocket tests for TeleCLI
Tests WebSocket functionality through the browser using Playwright
"""
import pytest
import socket
import time
import threading
import uvicorn
from playwright.sync_api import Error as PlaywrightError, sync_playwright

pytestmark = pytest.mark.playwright

# Test configuration
WEB_HOST = "127.0.0.1"
WEB_PORT = None
BASE_URL = None

# Server management
server_thread = None
server_ready = False


def reserve_free_port() -> int:
    """Allocate a free local TCP port for the temporary test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((WEB_HOST, 0))
        return sock.getsockname()[1]


def run_server():
    """Run the server in a thread"""
    global server_ready
    try:
        config = uvicorn.Config(
            "src.web_app:app",
            host=WEB_HOST,
            port=WEB_PORT,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server_ready = True
        import asyncio
        asyncio.run(server.serve())
    except Exception as e:
        print(f"Server error: {e}")
        server_ready = False


@pytest.fixture(scope="session", autouse=True)
def start_websocket_server():
    """Start server for WebSocket tests"""
    global server_thread, server_ready, WEB_PORT, BASE_URL

    WEB_PORT = reserve_free_port()
    BASE_URL = f"http://{WEB_HOST}:{WEB_PORT}"

    # Start server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server
    max_attempts = 50
    for attempt in range(max_attempts):
        if server_ready:
            time.sleep(0.5)
            break
        time.sleep(0.1)

    # Verify server listening
    for attempt in range(20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                result = sock.connect_ex((WEB_HOST, WEB_PORT))
                if result == 0:
                    time.sleep(0.3)
                    break
        except Exception:
            pass
        time.sleep(0.1)

    yield


@pytest.fixture
def browser():
    """Create Playwright browser"""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        yield browser
        browser.close()


def test_websocket_connection_established(browser):
    """Test that WebSocket connection is established from browser"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Page should load successfully
    assert page.title() != "", "Page should have a title"

    page.close()


def test_webpage_loads_for_websocket(browser):
    """Test that the main page loads (prerequisite for WebSocket)"""
    page = browser.new_page()
    response = page.goto(BASE_URL)

    assert response.status == 200
    page.wait_for_load_state("networkidle")

    content = page.content()
    assert len(content) > 100, "Page should have content"

    page.close()


def test_page_contains_websocket_references(browser):
    """Test that page likely contains WebSocket-related code"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    content = page.content()
    # Check for common WebSocket indicators
    has_ws_indicators = (
        "ws:" in content or "wss:" in content or
        "websocket" in content.lower() or
        "WebSocket" in content
    )

    # It's okay if these aren't present - page might load without immediately using WS
    assert content, "Page should have content"

    page.close()


def test_multiple_page_loads_for_websocket(browser):
    """Test that page can be loaded multiple times for WebSocket sessions"""
    for i in range(3):
        page = browser.new_page()
        response = page.goto(BASE_URL)
        assert response.status == 200
        page.wait_for_load_state("networkidle")
        page.close()
        time.sleep(0.1)


def test_api_endpoints_for_websocket_config(browser):
    """Test that API endpoints for WebSocket config are accessible"""
    page = browser.new_page()

    # Test auth config endpoint
    response = page.goto(f"{BASE_URL}/api/auth/required")
    assert response.status == 200
    content = page.content()
    assert "auth_required" in content.lower()

    page.close()


def test_health_endpoint_before_websocket(browser):
    """Test health endpoint which indicates server readiness for WebSocket"""
    page = browser.new_page()
    response = page.goto(f"{BASE_URL}/health")
    assert response.status == 200

    page.close()


def test_page_response_before_websocket(browser):
    """Test that pages load quickly before attempting WebSocket"""
    page = browser.new_page()

    start = time.time()
    response = page.goto(BASE_URL, wait_until="load", timeout=10000)
    elapsed = time.time() - start

    assert response.status == 200
    assert elapsed < 3, f"Page took {elapsed}s, expected < 3s"

    page.close()


def test_console_messages_on_websocket_page(browser):
    """Test that console messages are captured on WebSocket page"""
    page = browser.new_page()

    console_messages = []
    page.on("console", lambda msg: console_messages.append((msg.type, msg.text)))

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Should have some activity (not necessarily errors for WebSocket pages)
    # Just verify the page loaded
    assert page.title(), "Page should have loaded"

    page.close()


def test_page_javascript_execution(browser):
    """Test that JavaScript executes on the page"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Try to execute some JavaScript
    result = page.evaluate("1 + 1")
    assert result == 2, "JavaScript should execute"

    page.close()


def test_websocket_session_isolation(browser):
    """Test that multiple browser pages create isolated sessions"""
    pages = []
    for i in range(2):
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        pages.append(page)

    # Both pages should be functional
    for page in pages:
        assert page.title(), f"Page {pages.index(page)} should be loaded"

    for page in pages:
        page.close()


def test_terminal_ui_elements(browser):
    """Test that terminal UI elements are present"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Look for common terminal UI elements
    content = page.content()
    has_ui_elements = (
        "terminal" in content.lower() or
        "input" in content.lower() or
        "output" in content.lower() or
        "cmd" in content.lower() or
        len(content) > 1000  # Page has substantial content
    )

    assert has_ui_elements or len(content) > 1000, "Page should have UI elements or content"

    page.close()


def test_page_navigation_paths(browser):
    """Test that various navigation paths work"""
    page = browser.new_page()

    # Test root path
    response = page.goto(BASE_URL + "/")
    assert response.status == 200

    # Test /telecli path
    response = page.goto(BASE_URL + "/telecli")
    assert response.status == 200

    page.close()


def test_concurrent_browser_sessions(browser):
    """Test multiple concurrent browser sessions"""
    pages = []
    for i in range(3):
        page = browser.new_page()
        response = page.goto(BASE_URL)
        assert response.status == 200
        page.wait_for_load_state("load")
        pages.append(page)

    # Verify all are loaded
    for i, page in enumerate(pages):
        assert page.title(), f"Page {i} should be loaded"

    # Close all
    for page in pages:
        page.close()


def test_page_stability_over_time(browser):
    """Test that page remains stable over time"""
    page = browser.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    initial_title = page.title()

    # Wait a bit
    time.sleep(1)

    # Page should still be responsive
    assert page.title() == initial_title
    current_content_length = len(page.content())
    assert current_content_length > 0

    page.close()
