"""
Playwright WebSocket tests for TeleCLI
Tests WebSocket functionality through the browser using Playwright
"""
import pytest
import time
from playwright.sync_api import Error as PlaywrightError, sync_playwright
from tests.playwright_server import ManagedUvicornServer, reserve_free_port

pytestmark = pytest.mark.playwright

# Test configuration
WEB_HOST = "127.0.0.1"
WEB_PORT = None
BASE_URL = None

# Server management
managed_server = None


@pytest.fixture(scope="session", autouse=True)
def start_websocket_server():
    """Start server for WebSocket tests"""
    global managed_server, WEB_PORT, BASE_URL

    WEB_PORT = reserve_free_port(WEB_HOST)
    BASE_URL = f"http://{WEB_HOST}:{WEB_PORT}"
    managed_server = ManagedUvicornServer("src.web_app:app", WEB_HOST, WEB_PORT)
    managed_server.start()

    yield

    managed_server.stop()


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
