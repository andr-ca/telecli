# P0 Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Implement 4 critical security fixes (command filtering, authentication, client ID randomness, SSL/TLS) to prevent command injection, unauthorized access, and session hijacking.

**Architecture:**
- **Client ID Fix**: Replace weak JavaScript randomness with crypto.getRandomValues()
- **SSL/TLS Fix**: Connect existing config values to uvicorn server initialization
- **Command Filtering**: Create centralized CommandFilter class, validate all terminal input
- **Authentication**: Add WebSocket auth middleware, enforce AUTH_TOKEN on handshake

**Tech Stack:** FastAPI, Pydantic, asyncio, Python logging, JavaScript crypto API

**Estimated Time:** 8-10 hours total (4 independent fixes, can parallelize)

---

## Fix 1: Cryptographically Secure Client ID (JavaScript)

**Priority:** P0 | **Time:** 30 minutes | **Risk:** Low (frontend only)

### Task 1.1: Update index.html with crypto.getRandomValues()

**Files:**
- Modify: `static/index.html:71`

**Step 1: Review current implementation**

Current code at line 71:
```javascript
const clientId = 'web-' + Math.random().toString(36).substr(2, 9);
```

This produces only ~30 bits of entropy (predictable).

**Step 2: Replace with crypto-secure randomness**

Replace line 71 with:
```javascript
const clientId = 'web-' + crypto.getRandomValues(new Uint8Array(16))
    .reduce((hex, byte) => hex + byte.toString(16).padStart(2, '0'), '');
```

This produces 128 bits of entropy (2^128 possible IDs).

**Step 3: Verify syntax in browser**

Open `static/index.html` in browser console and verify:
```javascript
// Should print different 32-char ID each time
console.log('web-' + crypto.getRandomValues(new Uint8Array(16))
    .reduce((hex, byte) => hex + byte.toString(16).padStart(2, '0'), ''));
```

Expected: 32 hexadecimal characters (128 bits)

**Step 4: Commit**

```bash
git add static/index.html
git commit -m "security: use cryptographically secure client ID generation

- Replace Math.random() with crypto.getRandomValues()
- Increase entropy from 30 bits to 128 bits
- Prevents session hijacking via client ID prediction"
```

---

## Fix 2: SSL/TLS Configuration

**Priority:** P0 | **Time:** 1-1.5 hours | **Risk:** Low (config only)

### Task 2.1: Add float config helper

**Files:**
- Modify: `src/config.py:13-23`

**Step 1: Add _get_float helper function**

After the `_get_int` function (around line 24), add:

```python
def _get_float(key: str, default: float, min_value: float = None, max_value: float = None) -> float:
    """Safe float conversion from environment variable with validation"""
    try:
        value = float(os.getenv(key, default))
        if min_value is not None and value < min_value:
            raise ValueError(f"Value {value} is less than minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Value {value} is greater than maximum {max_value}")
        return value
    except ValueError as e:
        raise ValueError(f"Invalid {key}: {e}. Expected float, got '{os.getenv(key)}'")
```

**Step 2: Commit helper function**

```bash
git add src/config.py
git commit -m "chore: add _get_float config helper for type safety"
```

### Task 2.2: Add SSL/TLS validation to Config

**Files:**
- Modify: `src/config.py:81-113` (validate method)

**Step 1: Add SSL validation to Config.validate() method**

In the `validate()` classmethod, add this before the final return (after line 113):

```python
        # Validate SSL configuration
        if cls.WEB_SSL_CERT and not cls.WEB_SSL_KEY:
            raise ValueError("WEB_SSL_KEY required if WEB_SSL_CERT is set")
        if cls.WEB_SSL_KEY and not cls.WEB_SSL_CERT:
            raise ValueError("WEB_SSL_CERT required if WEB_SSL_KEY is set")

        # Verify SSL files exist if specified
        if cls.WEB_SSL_CERT:
            if not Path(cls.WEB_SSL_CERT).exists():
                raise ValueError(f"SSL certificate file not found: {cls.WEB_SSL_CERT}")
        if cls.WEB_SSL_KEY:
            if not Path(cls.WEB_SSL_KEY).exists():
                raise ValueError(f"SSL key file not found: {cls.WEB_SSL_KEY}")
```

**Step 2: Add imports at top of file**

Verify these imports exist at top of `config.py`:
```python
from pathlib import Path
```

(It should already be there from line 7)

**Step 3: Test validation**

Create a test script `/tmp/test_ssl_validation.py`:
```python
import sys
sys.path.insert(0, '/home/andrey/projects/telecli')

# Test 1: Both cert and key missing (OK)
from src.config import Config
try:
    # This should pass since neither are set in .env
    Config.validate()
    print("✓ Test 1 passed: No SSL configured")
except ValueError as e:
    print(f"✗ Test 1 failed: {e}")

# Test 2: Cert without key (should fail)
import os
os.environ['WEB_SSL_CERT'] = '/tmp/test.crt'
# Clear module cache to reload
if 'src.config' in sys.modules:
    del sys.modules['src.config']
from src.config import Config as Config2
try:
    Config2.validate()
    print("✗ Test 2 failed: Should require WEB_SSL_KEY")
except ValueError as e:
    print(f"✓ Test 2 passed: {e}")
```

Run:
```bash
cd /home/andrey/projects/telecli
python3 /tmp/test_ssl_validation.py
```

Expected output:
```
✓ Test 1 passed: No SSL configured
✓ Test 2 passed: WEB_SSL_KEY required if WEB_SSL_CERT is set
```

**Step 4: Commit SSL validation**

```bash
git add src/config.py
git commit -m "security: add SSL/TLS configuration validation

- Validate cert and key both present or both absent
- Verify SSL files exist at startup
- Prevents misconfiguration in production"
```

### Task 2.3: Pass SSL config to Uvicorn

**Files:**
- Modify: `src/main.py:44-50`

**Step 1: Update uvicorn.Config call**

Replace lines 44-50:

```python
    # Create web server task
    config = uvicorn.Config(
        web_app,
        host=Config.WEB_HOST,
        port=Config.WEB_PORT,
        log_level="info",
        ssl_certfile=Config.WEB_SSL_CERT if Config.WEB_SSL_CERT else None,
        ssl_keyfile=Config.WEB_SSL_KEY if Config.WEB_SSL_KEY else None,
    )
```

**Step 2: Verify no syntax errors**

Run:
```bash
cd /home/andrey/projects/telecli
python3 -m py_compile src/main.py
echo "✓ Syntax check passed"
```

Expected: No output (success)

**Step 3: Test with self-signed cert (optional but recommended)**

```bash
# Generate self-signed certificate for testing
cd /tmp
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=localhost"

# Try running with cert
cd /home/andrey/projects/telecli
WEB_SSL_CERT=/tmp/cert.pem WEB_SSL_KEY=/tmp/key.pem python3 -c \
  "from src.config import Config; Config.validate(); print('✓ SSL config valid')"
```

Expected: `✓ SSL config valid`

**Step 4: Commit SSL to Uvicorn**

```bash
git add src/main.py
git commit -m "security: pass SSL/TLS config to uvicorn server

- Connect WEB_SSL_CERT and WEB_SSL_KEY to server initialization
- Server now enforces HTTPS when cert/key provided
- Prevents unencrypted data transmission"
```

---

## Fix 3: Command Filtering

**Priority:** P0 | **Time:** 2-3 hours | **Risk:** Medium (new validation logic)

### Task 3.1: Create CommandFilter class

**Files:**
- Create: `src/command_filter.py`
- Create: `tests/test_command_filter.py`

**Step 1: Write failing test**

Create `tests/test_command_filter.py`:

```python
"""Tests for command filtering"""
import pytest
from src.command_filter import CommandFilter


def test_filter_allows_all_when_disabled():
    """When filter disabled, all commands allowed"""
    f = CommandFilter(allowed_only=False, allowed_file="")
    assert f.is_allowed("rm -rf /")
    assert f.is_allowed("dangerous-command")
    assert f.is_allowed("")


def test_filter_blocks_unlisted_when_enabled():
    """When filter enabled, only listed commands allowed"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls", "cat", "grep"}  # Manually set for test
    assert f.is_allowed("ls /tmp")
    assert f.is_allowed("cat file.txt")
    assert not f.is_allowed("rm file.txt")
    assert not f.is_allowed("rm -rf /")


def test_filter_extracts_command_name():
    """Extract first word as command name"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"grep"}
    assert f.is_allowed("grep 'pattern' file.txt")
    assert not f.is_allowed("grep-recursive file.txt")  # Different command


def test_filter_handles_whitespace():
    """Handle leading/trailing whitespace"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls"}
    assert f.is_allowed("  ls  /tmp  ")
    assert f.is_allowed("ls")


def test_filter_loads_file():
    """Load allowed commands from file"""
    import tempfile
    import os

    # Create temp file with allowed commands
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("ls\ncat\ngrep\n")
        f.write("# Comments are ignored\n")
        f.write("\n")  # Empty lines
        f.write("  find  \n")  # With whitespace
        temp_file = f.name

    try:
        f = CommandFilter(allowed_only=True, allowed_file=temp_file)
        assert f.is_allowed("ls /tmp")
        assert f.is_allowed("cat file.txt")
        assert f.is_allowed("grep pattern file.txt")
        assert f.is_allowed("find /")
        assert not f.is_allowed("rm -rf /")
    finally:
        os.unlink(temp_file)


def test_filter_empty_command():
    """Handle empty command string"""
    f = CommandFilter(allowed_only=True, allowed_file="")
    f.allowed_commands = {"ls"}
    assert not f.is_allowed("")
    assert not f.is_allowed("   ")
```

Run to verify it fails:
```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_command_filter.py -v
```

Expected: All tests FAIL with "No module named 'src.command_filter'"

**Step 2: Write minimal CommandFilter implementation**

Create `src/command_filter.py`:

```python
"""Command filtering for security - prevent arbitrary command execution"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CommandFilter:
    """Validates commands against allowed list"""

    def __init__(self, allowed_only: bool, allowed_file: str):
        """
        Args:
            allowed_only: If True, only allow listed commands
            allowed_file: Path to file with allowed commands (one per line)
        """
        self.allowed_only = allowed_only
        self.allowed_commands = set()

        if allowed_only and allowed_file:
            self._load_allowed_commands(allowed_file)

    def _load_allowed_commands(self, filepath: str) -> None:
        """Load allowed commands from file"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        self.allowed_commands.add(line)

            logger.info(f"Loaded {len(self.allowed_commands)} allowed commands from {filepath}")
        except FileNotFoundError:
            logger.error(f"Allowed commands file not found: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Error loading allowed commands: {e}")
            raise

    def is_allowed(self, command: str) -> bool:
        """
        Check if command is allowed

        Args:
            command: Full command string (e.g., "ls -la /tmp")

        Returns:
            True if command is allowed, False otherwise
        """
        # If filtering disabled, allow everything
        if not self.allowed_only:
            return True

        # Extract command name (first word)
        command = command.strip()
        if not command:
            return False

        cmd_name = command.split()[0]

        # Check if command is in allowed list
        is_allowed = cmd_name in self.allowed_commands

        if not is_allowed:
            logger.warning(f"Command not allowed: {cmd_name} (from: {command[:50]})")

        return is_allowed

    def get_status(self) -> dict:
        """Get filter status for logging/debugging"""
        return {
            "enabled": self.allowed_only,
            "num_allowed": len(self.allowed_commands),
            "allowed_commands": sorted(list(self.allowed_commands))
        }
```

**Step 3: Run tests to verify they pass**

```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_command_filter.py -v
```

Expected: All tests PASS

**Step 4: Commit CommandFilter class**

```bash
git add src/command_filter.py tests/test_command_filter.py
git commit -m "security: add CommandFilter class for command validation

- Load allowed commands from configurable file
- Validate all terminal input against whitelist when enabled
- Support both allow-all and whitelist modes
- Full test coverage with file loading and edge cases"
```

### Task 3.2: Integrate CommandFilter into Config

**Files:**
- Modify: `src/config.py:26-79`

**Step 1: Add CommandFilter import and initialization**

At the top of `src/config.py`, after line 7 (after imports), add:

```python
from src.command_filter import CommandFilter
```

**Step 2: Add command_filter attribute to Config class**

In the `Config` class, after the security config (after line 60), add:

```python
    # Command filtering (lazily initialized)
    command_filter: Optional[CommandFilter] = None
```

You'll also need to add `Optional` to the imports:
```python
from typing import Optional
```

**Step 3: Initialize CommandFilter in validate()**

In the `validate()` classmethod, add this before the final return (after SSL validation):

```python
        # Initialize command filter
        if cls.ALLOWED_COMMANDS_ONLY:
            if not cls.ALLOWED_COMMANDS_FILE:
                raise ValueError("ALLOWED_COMMANDS_FILE required when ALLOWED_COMMANDS_ONLY is true")
            cls.command_filter = CommandFilter(True, cls.ALLOWED_COMMANDS_FILE)
            logger.info(f"Command filtering enabled: {cls.command_filter.get_status()['num_allowed']} allowed commands")
        else:
            cls.command_filter = CommandFilter(False, "")
            logger.info("Command filtering disabled (all commands allowed)")
```

**Step 4: Verify syntax**

```bash
cd /home/andrey/projects/telecli
python3 -m py_compile src/config.py
echo "✓ Config syntax check passed"
```

**Step 5: Test initialization**

Create test script `/tmp/test_config_filter.py`:

```python
import sys
import os
sys.path.insert(0, '/home/andrey/projects/telecli')

# Clear module cache
for mod in list(sys.modules.keys()):
    if 'src' in mod:
        del sys.modules[mod]

# Test 1: Filter disabled (default)
os.environ['ALLOWED_COMMANDS_ONLY'] = 'false'
from src.config import Config
Config.validate()
print(f"✓ Test 1: Filter disabled, status = {Config.command_filter.get_status()}")

# Test 2: Filter enabled requires file
os.environ['ALLOWED_COMMANDS_ONLY'] = 'true'
os.environ['ALLOWED_COMMANDS_FILE'] = ''
for mod in list(sys.modules.keys()):
    if 'src' in mod:
        del sys.modules[mod]

try:
    from src.config import Config as Config2
    Config2.validate()
    print("✗ Test 2 failed: Should require file")
except ValueError as e:
    print(f"✓ Test 2: {e}")
```

Run:
```bash
cd /home/andrey/projects/telecli
python3 /tmp/test_config_filter.py
```

Expected:
```
✓ Test 1: Filter disabled, status = {'enabled': False, ...}
✓ Test 2: ALLOWED_COMMANDS_FILE required when ALLOWED_COMMANDS_ONLY is true
```

**Step 6: Commit Config integration**

```bash
git add src/config.py
git commit -m "security: integrate CommandFilter into Config

- Initialize command filter during startup
- Validate configuration (require file when filtering enabled)
- Log filter status for debugging"
```

### Task 3.3: Enforce filtering in terminal.send_input()

**Files:**
- Modify: `src/terminal.py:116-144`
- Modify: `tests/test_terminal.py`

**Step 1: Write test for command validation**

Add to `tests/test_terminal.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.terminal import TerminalSession
from src.config import Config


@pytest.mark.asyncio
async def test_send_input_blocked_by_filter():
    """send_input should check command filter before sending"""
    session = TerminalSession("test-123")
    session.process = AsyncMock()
    session.is_active = True

    # Mock filter to block the command
    with patch.object(Config, 'command_filter') as mock_filter:
        mock_filter.is_allowed.return_value = False

        with pytest.raises(RuntimeError, match="Command not allowed"):
            await session.send_input("rm -rf /")

        # Verify filter was checked
        mock_filter.is_allowed.assert_called_once()


@pytest.mark.asyncio
async def test_send_input_allowed_by_filter():
    """send_input should work when filter allows"""
    session = TerminalSession("test-123")
    session.process = AsyncMock()
    session.is_active = True

    # Mock filter to allow the command
    with patch.object(Config, 'command_filter') as mock_filter:
        mock_filter.is_allowed.return_value = True

        # Should not raise
        await session.send_input("ls /tmp")
```

Run to verify it fails:
```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_terminal.py::test_send_input_blocked_by_filter -v
```

Expected: FAIL (command filter check not yet implemented)

**Step 2: Add command filter check to send_input()**

In `src/terminal.py`, in the `send_input()` method (starting at line 116), add this check right after the activity check:

```python
    async def send_input(self, text: str, newline: bool = True) -> None:
        """
        Send input to the terminal immediately
        Supports special control characters like Ctrl+C
        """
        if not self.is_active or not self.process:
            raise RuntimeError("Session is not active")

        # ADD THIS: Check command filter (unless it's a special control character)
        if text not in ('\x03', '\x04', '\r', '\n') and Config.command_filter:
            if not Config.command_filter.is_allowed(text):
                raise RuntimeError(f"Command not allowed: {text[:50]}")

        try:
            # ... rest of method unchanged
```

**Step 3: Run tests to verify they pass**

```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_terminal.py::test_send_input_blocked_by_filter -v
python3 -m pytest tests/test_terminal.py::test_send_input_allowed_by_filter -v
```

Expected: Both PASS

**Step 4: Verify imports in terminal.py**

Check that `src/terminal.py` already imports Config (should be at line 9):
```python
from src.config import Config
```

If not present, add it.

**Step 5: Run all existing terminal tests**

```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_terminal.py -v
```

Expected: All tests PASS (new tests pass, old tests still work)

**Step 6: Commit filter enforcement**

```bash
git add src/terminal.py tests/test_terminal.py
git commit -m "security: enforce command filtering in terminal.send_input()

- Check Config.command_filter before sending any terminal input
- Allow special control characters (Ctrl+C, Ctrl+D, newlines)
- Raise RuntimeError if command not allowed
- Full test coverage for allowed/blocked scenarios"
```

### Task 3.4: Create example allowed commands file

**Files:**
- Create: `.env.sample` update
- Create: `examples/allowed_commands.txt`

**Step 1: Create example allowed commands file**

Create `examples/allowed_commands.txt`:

```
# TeleCLI Allowed Commands
# Each line is a command name that users can run
# Everything after # is a comment
# Empty lines are ignored

# File operations (safe)
ls
cat
grep
find
head
tail
wc

# Navigation
cd
pwd
echo

# Development
python3
node
npm
git
docker

# System monitoring (read-only)
ps
top
whoami
date
uname

# Network
ping
curl
wget
netstat

# Text processing
sed
awk
cut
sort
uniq
```

**Step 2: Update .env.sample**

Modify `.env.sample` to show command filtering:

Find the "Security Configuration" section and update it to:

```ini
# Security
AUTH_REQUIRED=false
AUTH_TOKEN=
ALLOWED_COMMANDS_ONLY=false
ALLOWED_COMMANDS_FILE=./examples/allowed_commands.txt
```

Add a comment above it:
```ini
# Security
# Set AUTH_REQUIRED=true to require token for WebSocket connections
# Set ALLOWED_COMMANDS_ONLY=true to enforce command whitelist (requires ALLOWED_COMMANDS_FILE)
AUTH_REQUIRED=false
AUTH_TOKEN=
ALLOWED_COMMANDS_ONLY=false
ALLOWED_COMMANDS_FILE=./examples/allowed_commands.txt
```

**Step 3: Update README with filtering info**

Add a section to `README.md` (or create SECURITY.md):

```markdown
## Security Features

### Command Filtering

Enable command whitelisting to prevent arbitrary command execution:

```ini
ALLOWED_COMMANDS_ONLY=true
ALLOWED_COMMANDS_FILE=./examples/allowed_commands.txt
```

When enabled, only commands in the whitelist can be executed.
See `examples/allowed_commands.txt` for the default list.

### Authentication

Require authentication tokens for terminal access:

```ini
AUTH_REQUIRED=true
AUTH_TOKEN=your-strong-random-token
```

### SSL/TLS

Enable HTTPS by providing certificate and key paths:

```ini
WEB_SSL_CERT=/path/to/cert.pem
WEB_SSL_KEY=/path/to/key.pem
```
```

**Step 4: Commit example files**

```bash
git add examples/allowed_commands.txt .env.sample README.md
git commit -m "docs: add command filtering documentation and examples

- Create example allowed_commands.txt with safe command set
- Update .env.sample with filtering configuration
- Add security features section to README"
```

---

## Fix 4: Authentication (WebSocket + Telegram)

**Priority:** P0 | **Time:** 2-3 hours | **Risk:** Medium (affects all connections)

### Task 4.1: Add WebSocket authentication middleware

**Files:**
- Modify: `src/web_app.py:91-220`
- Create: `tests/test_web_app_auth.py`

**Step 1: Write failing test for auth**

Create `tests/test_web_app_auth.py`:

```python
"""Tests for WebSocket authentication"""
import pytest
from fastapi.testclient import TestClient
from src.web_app import app
from src.config import Config
from unittest.mock import patch


def test_websocket_accepts_without_auth_when_disabled():
    """WebSocket should accept when AUTH_REQUIRED=false"""
    with patch.object(Config, 'AUTH_REQUIRED', False):
        client = TestClient(app)
        with client.websocket_connect("/ws/test-client") as websocket:
            # Should connect successfully
            data = websocket.receive_json()
            # Connection established


def test_websocket_requires_auth_when_enabled():
    """WebSocket should reject when AUTH_REQUIRED=true and no token"""
    with patch.object(Config, 'AUTH_REQUIRED', True):
        with patch.object(Config, 'AUTH_TOKEN', 'secret-token'):
            client = TestClient(app)

            # Try without token - should fail
            with pytest.raises(Exception):  # WebSocket connection refused
                with client.websocket_connect("/ws/test-client") as websocket:
                    pass


def test_websocket_accepts_with_valid_token():
    """WebSocket should accept with valid token"""
    with patch.object(Config, 'AUTH_REQUIRED', True):
        with patch.object(Config, 'AUTH_TOKEN', 'secret-token'):
            client = TestClient(app)

            # Try with token - should succeed
            with client.websocket_connect("/ws/test-client?token=secret-token") as websocket:
                # Should connect successfully
                pass


def test_websocket_rejects_invalid_token():
    """WebSocket should reject with invalid token"""
    with patch.object(Config, 'AUTH_REQUIRED', True):
        with patch.object(Config, 'AUTH_TOKEN', 'secret-token'):
            client = TestClient(app)

            # Try with wrong token - should fail
            with pytest.raises(Exception):  # WebSocket connection refused
                with client.websocket_connect("/ws/test-client?token=wrong-token") as websocket:
                    pass
```

Run to verify it fails:
```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_web_app_auth.py::test_websocket_requires_auth_when_enabled -v
```

Expected: FAIL (auth check not implemented yet)

**Step 2: Add auth check to WebSocket endpoint**

In `src/web_app.py`, modify the `websocket_endpoint` function (starting at line 91):

Replace the first few lines with:

```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for bidirectional terminal streaming"""

    # ADD THIS: Check authentication if required
    if Config.AUTH_REQUIRED:
        token = websocket.query_params.get("token")
        if not token or token != Config.AUTH_TOKEN:
            logger.warning(f"WebSocket auth failed for {client_id}: invalid or missing token")
            await websocket.close(code=1008, reason="Unauthorized")
            return

    await websocket.accept()
    logger.info(f"WebSocket connection established for client {client_id}")

    # ... rest of function unchanged
```

**Step 3: Update client-side to send token**

In `static/index.html`, modify the `getWebSocketUrl()` function (around line 133):

Replace with:

```javascript
function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const authRequired = true; // Or check from server config endpoint

    let token = '';
    if (authRequired) {
        // Try to get token from localStorage
        token = localStorage.getItem('terminal-auth-token');
        if (!token) {
            token = prompt("Enter authentication token:") || "";
            if (token) {
                localStorage.setItem('terminal-auth-token', token);
            }
        }
    }

    const url = `${protocol}//${window.location.host}/ws/${clientId}`;
    return token ? `${url}?token=${encodeURIComponent(token)}` : url;
}
```

**Step 4: Add auth status display**

In `static/index.html`, add display of auth status in the header (around line 23):

Add a new div after the proxy-status div:

```html
            <div id="auth-status" style="margin-top: 5px; font-size: 12px; color: #b0b0b0;"></div>
```

Add this JavaScript to display auth info:

In the script section, add after `connectWebSocket()` call (around line 301):

```javascript
        // Check if auth is required
        fetch('/api/auth/required')
            .then(r => r.json())
            .then(data => {
                if (data.auth_required) {
                    document.getElementById('auth-status').textContent = '🔒 Authentication enabled';
                }
            })
            .catch(e => console.debug('Auth check not available'));
```

**Step 5: Add API endpoint for auth status**

In `src/web_app.py`, add this endpoint (after the `/health` endpoint around line 60):

```python
@app.get("/api/auth/required")
async def get_auth_required():
    """Get whether authentication is required"""
    return {
        "auth_required": Config.AUTH_REQUIRED
    }
```

**Step 6: Run auth tests**

```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_web_app_auth.py -v
```

Expected: Tests related to auth scenarios PASS

**Step 7: Commit WebSocket auth**

```bash
git add src/web_app.py static/index.html tests/test_web_app_auth.py
git commit -m "security: add WebSocket authentication

- Check AUTH_TOKEN in query params when AUTH_REQUIRED=true
- Reject connections with invalid/missing token (code 1008)
- Update client to prompt for and cache auth token
- Add /api/auth/required endpoint to inform client
- Full test coverage for auth scenarios"
```

### Task 4.2: Add Telegram authentication

**Files:**
- Modify: `src/telegram_bot.py:14-76`
- Modify: `.env.sample`

**Step 1: Add user ID whitelist to Config**

In `src/config.py`, add to Security Configuration section (after line 60):

```python
    # Telegram user whitelist (comma-separated user IDs)
    ALLOWED_TELEGRAM_USERS = os.getenv("ALLOWED_TELEGRAM_USERS", "").strip()
```

**Step 2: Update .env.sample**

Add to the Telegram Configuration section in `.env.sample`:

```ini
# Telegram - Optional user ID whitelist (comma-separated)
# Leave empty to allow all users
ALLOWED_TELEGRAM_USERS=
```

**Step 3: Add user check to Telegram bot**

In `src/telegram_bot.py`, add this helper function near the top (after imports, around line 13):

```python
def is_telegram_user_allowed(user_id: int) -> bool:
    """Check if Telegram user is in whitelist"""
    if not Config.ALLOWED_TELEGRAM_USERS:
        return True  # Whitelist disabled

    allowed_ids = set(
        int(uid.strip()) for uid in Config.ALLOWED_TELEGRAM_USERS.split(',')
        if uid.strip()
    )

    return user_id in allowed_ids
```

**Step 4: Add auth check to each command handler**

Modify each command handler in `telegram_bot.py` to check auth:

For `async def start()` (line 16):
```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user_id = update.effective_user.id

    # ADD THIS:
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot")
        logger.warning(f"Unauthorized Telegram user: {user_id}")
        return

    await update.message.reply_text(
        # ... rest unchanged
```

Repeat for `async def help_command()` and `async def reset_command()` and `async def handle_message()`:

```python
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    # ... rest


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        return
    # ... rest


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular messages (commands)"""
    user_id = update.effective_user.id
    if not is_telegram_user_allowed(user_id):
        await update.message.reply_text("❌ Unauthorized")
        logger.warning(f"Unauthorized Telegram user: {user_id}")
        return
    # ... rest
```

**Step 5: Test user filtering**

Create test script `/tmp/test_telegram_auth.py`:

```python
import sys
sys.path.insert(0, '/home/andrey/projects/telecli')

import os
os.environ['ALLOWED_TELEGRAM_USERS'] = '123,456,789'

from src.telegram_bot import is_telegram_user_allowed

assert is_telegram_user_allowed(123), "User 123 should be allowed"
assert is_telegram_user_allowed(456), "User 456 should be allowed"
assert not is_telegram_user_allowed(999), "User 999 should NOT be allowed"
print("✓ All auth checks passed")

# Test with whitelist disabled
os.environ['ALLOWED_TELEGRAM_USERS'] = ''
import importlib
import src.config
importlib.reload(src.config)
from src.config import Config
from src.telegram_bot import is_telegram_user_allowed as is_allowed_2
assert is_allowed_2(999), "Any user should be allowed when whitelist empty"
print("✓ Disabled whitelist works")
```

Run:
```bash
cd /home/andrey/projects/telecli
python3 /tmp/test_telegram_auth.py
```

Expected:
```
✓ All auth checks passed
✓ Disabled whitelist works
```

**Step 6: Verify syntax**

```bash
cd /home/andrey/projects/telecli
python3 -m py_compile src/telegram_bot.py
echo "✓ Telegram bot syntax check passed"
```

**Step 7: Commit Telegram auth**

```bash
git add src/telegram_bot.py src/config.py .env.sample
git commit -m "security: add Telegram user whitelisting

- Add ALLOWED_TELEGRAM_USERS config for optional user ID whitelist
- Check user ID in all command handlers
- Reject unauthorized users with warning
- Support comma-separated user IDs in config"
```

### Task 4.3: Add auth status logging

**Files:**
- Modify: `src/main.py:26-38`

**Step 1: Log auth configuration at startup**

In `src/main.py`, in the `main()` function, after the existing config log lines (around line 38), add:

```python
    logger.info(f"  - Authentication: {'Required' if Config.AUTH_REQUIRED else 'Disabled'}")
    if Config.ALLOWED_COMMANDS_ONLY:
        logger.info(f"  - Command filtering: Enabled ({Config.command_filter.get_status()['num_allowed']} allowed commands)")
    else:
        logger.info(f"  - Command filtering: Disabled (all commands allowed)")
    if Config.ALLOWED_TELEGRAM_USERS:
        logger.info(f"  - Telegram whitelist: Enabled ({len(Config.ALLOWED_TELEGRAM_USERS.split(','))} users)")
    else:
        logger.info(f"  - Telegram whitelist: Disabled (all users allowed)")
```

**Step 2: Verify logging**

Run the app with debug output:
```bash
cd /home/andrey/projects/telecli
LOG_LEVEL=DEBUG python3 src/main.py 2>&1 | grep -E "(Authentication|Command filtering|Telegram)"
```

Expected: See auth status lines in startup output

**Step 3: Commit auth logging**

```bash
git add src/main.py
git commit -m "chore: log authentication status at startup

- Display auth requirement status
- Show command filtering configuration
- Show Telegram whitelist status"
```

---

## Validation & Testing

### Pre-Implementation Checklist
- [ ] All 4 fixes have been planned above
- [ ] All file paths are exact
- [ ] All code samples are complete
- [ ] All tests are written before implementation
- [ ] All commit messages follow format

### Post-Implementation Testing

**Unit Tests:**
```bash
cd /home/andrey/projects/telecli
python3 -m pytest tests/test_command_filter.py -v
python3 -m pytest tests/test_web_app_auth.py -v
python3 -m pytest tests/test_terminal.py -v
```

Expected: All tests PASS

**Integration Tests:**

1. **Test Command Filtering:**
```bash
# In .env
ALLOWED_COMMANDS_ONLY=true
ALLOWED_COMMANDS_FILE=./examples/allowed_commands.txt

# Should work:
python3 -c "from src.config import Config; Config.validate(); print('✓ Config valid')"

# In terminal, try:
ls    # Should work
rm -rf /  # Should be blocked
```

2. **Test Authentication:**
```bash
# In .env
AUTH_REQUIRED=true
AUTH_TOKEN=test-token-123

# In browser:
# - Visit http://localhost:8000
# - Should prompt for token
# - Enter wrong token: connection fails
# - Enter correct token: connection works
```

3. **Test SSL/TLS:**
```bash
# Generate test cert
openssl req -x509 -newkey rsa:2048 -keyout /tmp/key.pem -out /tmp/cert.pem \
  -days 365 -nodes -subj "/CN=localhost"

# In .env
WEB_SSL_CERT=/tmp/cert.pem
WEB_SSL_KEY=/tmp/key.pem

# App should start with HTTPS
python3 src/main.py
# Visit https://localhost:8000 (ignore browser warning about self-signed cert)
```

4. **Test Client ID Randomness:**
```bash
# Open browser console and run multiple times:
'web-' + crypto.getRandomValues(new Uint8Array(16))
  .reduce((hex, byte) => hex + byte.toString(16).padStart(2, '0'), '')
# Should get different 32-char hex string each time
```

### Security Validation Checklist
- [ ] Command filtering blocks dangerous commands
- [ ] Command filtering allows safe commands
- [ ] WebSocket requires auth when AUTH_REQUIRED=true
- [ ] WebSocket rejects invalid tokens
- [ ] Telegram bot blocks unauthorized users
- [ ] Client IDs are cryptographically random (test 10x, all different)
- [ ] SSL/TLS config is validated at startup
- [ ] All auth/filter config logged on startup

---

## Summary

| Fix | Files | Time | Tests |
|-----|-------|------|-------|
| 1. Client ID | `static/index.html` | 30m | Manual |
| 2. SSL/TLS | `src/config.py`, `src/main.py` | 1-1.5h | Config validation |
| 3. Command Filtering | New: `src/command_filter.py`, Modified: `src/config.py`, `src/terminal.py` | 2-3h | 8 tests |
| 4. Authentication | Modified: `src/web_app.py`, `src/telegram_bot.py`, `src/config.py`, `static/index.html` | 2-3h | 4+ tests |

**Total Effort:** 8-10 hours

---

## Next Steps After This Plan

Once implementation is complete:

1. **Testing**: Run full test suite and security validation checklist
2. **Code Review**: Have team review all auth/filter logic
3. **Load Testing**: Test with 50+ concurrent sessions
4. **Documentation**: Update SECURITY.md with setup instructions
5. **Deployment**: Deploy to production with monitoring

---

**Plan Version:** 1.0
**Created:** 2025-12-13
**Next Review:** After implementation complete
