"""
Pytest configuration for TeleCLI tests
Configures pytest-asyncio and shared fixtures
"""
import pytest
import os
import dotenv

# Load environment variables from .env file if it exists
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(dotenv_path):
    dotenv.load_dotenv(dotenv_path)

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# Set asyncio mode to auto (compatible with newer versions)
@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests"""
    import asyncio
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        # Windows compatibility
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_server: mark test as requiring server (deselect with '-m \"not requires_server\"')"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically add asyncio marker to async tests"""
    for item in items:
        if "asyncio" in item.keywords:
            continue
        if hasattr(item, "function") and hasattr(item.function, "__code__"):
            if "async" in item.function.__code__.co_names or item.function.__code__.co_flags & 0x100:
                item.add_marker(pytest.mark.asyncio)
