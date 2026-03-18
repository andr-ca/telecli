# Playwright Tests for TeleCLI

This document describes the Playwright test suite for validating TeleCLI's web functionality, including HTTP routing, WebSocket communication, and UI interactions.

## Overview

The test suite includes:

- **test_web_ui.py**: Tests for HTTP endpoints, CSS loading, page rendering, and UI responsiveness
- **test_websocket.py**: Tests for WebSocket connectivity, message handling, terminal input/output, and AI proxy integration

## Setup

### Prerequisites

1. Python 3.8+
2. Dependencies installed from `requirements.txt`

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium
```

## Running Tests

### Run All Tests

```bash
# Using the test runner script
python run_playwright_tests.py

# Or using pytest directly
pytest tests/test_web_ui.py tests/test_websocket.py -v
```

### Run Specific Test File

```bash
# Web UI tests only
pytest tests/test_web_ui.py -v

# WebSocket tests only
pytest tests/test_websocket.py -v
```

### Run Specific Test

```bash
# Single test
pytest tests/test_web_ui.py::test_root_path_serves_index_html -v

# With filter
pytest -k "websocket" -v
```

### Run with Different Options

```bash
# Show print statements
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -v -x

# Run with specific marker
pytest tests/ -v -m "asyncio"

# Generate HTML report
pytest tests/ --html=report.html --self-contained-html
```

## Test Categories

### Web UI Tests (`test_web_ui.py`)

| Test | Purpose |
|------|---------|
| `test_root_path_serves_index_html` | Verify GET / serves the web UI |
| `test_telecli_path_serves_index_html` | Verify GET /telecli serves the web UI |
| `test_style_css_loads` | Verify CSS is loaded correctly |
| `test_health_endpoint_returns_json` | Verify /health endpoint works |
| `test_debug_endpoint_returns_request_info` | Verify /debug endpoint returns request info |
| `test_stats_endpoint_returns_stats` | Verify /stats endpoint works |
| `test_api_sessions_endpoint` | Verify /api/sessions endpoint works |
| `test_api_auth_required_endpoint` | Verify /api/auth/required endpoint works |
| `test_api_ai_proxy_config_endpoint` | Verify /api/ai-proxy/config endpoint works |
| `test_api_llm_monitor_endpoint` | Verify /api/llm-monitor endpoint works |
| `test_page_loads_within_timeout` | Verify page loads in reasonable time |
| `test_telecli_path_without_trailing_slash` | Verify /telecli without trailing slash works |
| `test_console_errors_on_page_load` | Verify no critical console errors |

### WebSocket Tests (`test_websocket.py`)

| Test | Purpose |
|------|---------|
| `test_websocket_connection_accepted` | Verify WebSocket connection is accepted |
| `test_websocket_auth_required` | Verify auth handling in WebSocket |
| `test_websocket_receive_message` | Verify receiving messages from WebSocket |
| `test_websocket_terminal_input` | Verify sending terminal input |
| `test_websocket_resize_message` | Verify terminal resize handling |
| `test_websocket_ai_proxy_toggle` | Verify AI proxy enable/disable |
| `test_websocket_invalid_json` | Verify graceful handling of invalid JSON |
| `test_websocket_concurrent_messages` | Verify concurrent message handling |
| `test_websocket_ai_proxy_disable` | Verify disabling AI proxy |
| `test_websocket_via_browser` | Verify WebSocket works through browser |
| `test_websocket_connection_cleanup` | Verify proper resource cleanup |
| `test_websocket_multiple_clients` | Verify multiple concurrent clients |
| `test_websocket_llm_monitor_callback` | Verify LLM monitor callbacks |

## Environment Variables

Tests use these environment variables (can be configured in `.env`):

- `WEB_HOST`: Web server host (default: 127.0.0.1)
- `WEB_PORT`: Web server port (overridden per test for isolation)
- `LOG_LEVEL`: Logging level (set to WARNING during tests to reduce noise)
- `AUTH_REQUIRED`: Whether authentication is required (set to false during tests)

## Expected Behavior

### Test Server Startup

Each test file uses a `server_process` fixture that:
1. Starts the FastAPI server on a unique port
2. Waits for server to be ready (health check)
3. Runs the tests
4. Cleans up and terminates the server

This ensures test isolation and prevents port conflicts.

### Async Test Handling

WebSocket tests use `pytest-asyncio` for async/await support. Tests marked with `@pytest.mark.asyncio` run in an asyncio event loop.

## Troubleshooting

### Tests timeout
- Increase the timeout value in `pytest.ini`
- Check that the server is starting correctly
- Look for port conflicts

### Playwright browser not found
```bash
# Reinstall Playwright browsers
python -m playwright install chromium
```

### WebSocket tests failing
- Verify the server is running on the correct port
- Check that `AUTH_REQUIRED` is set to false in environment
- Look for firewall or network issues

### Import errors
```bash
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Playwright Tests
  run: |
    python -m playwright install chromium
    pytest tests/test_web_ui.py tests/test_websocket.py -v
```

### Local Development

For local testing during development:

```bash
# Watch mode (requires pytest-watch)
ptw tests/ -- -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Adding New Tests

To add new Playwright tests:

1. Create a test function in the appropriate test file
2. Use the `browser` fixture for UI tests or `server_process` + `client_id` for WebSocket tests
3. Add docstring describing what the test validates
4. Use appropriate pytest markers (`@pytest.mark.asyncio`, etc.)
5. Update this document with the new test

Example:

```python
def test_new_feature(browser):
    """Test that new feature works correctly"""
    page = browser.new_page()
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")

    # Test logic here
    assert True

    page.close()
```

## Performance Considerations

- Tests run on unique ports to avoid conflicts
- Server starts fresh for each test session
- WebSocket tests use reasonable timeouts (2-3 seconds)
- Tests clean up resources properly to prevent leaks

## Notes

- UI tests using Playwright's headless chromium are faster than browser-based testing
- WebSocket tests use both the `websockets` library (Python) and browser-based approaches
- Tests are designed to be independent and can run in parallel
- The test suite validates both happy paths and error conditions

## Further Reading

- [Playwright Documentation](https://playwright.dev/python/)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://github.com/pytest-dev/pytest-asyncio)
