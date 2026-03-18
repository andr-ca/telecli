#!/usr/bin/env python3
"""
Test runner for Playwright tests
Installs Playwright browsers and runs the test suite
"""
import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"{'=' * 60}")
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    print(f"\n✓ {description} completed successfully")
    return True


def main():
    """Main test runner"""
    # Ensure we're in the project root
    if not os.path.exists("src/web_app.py"):
        print("Error: Must run from project root directory")
        sys.exit(1)

    print("TeleCLI Playwright Test Suite")
    print("=" * 60)

    all_passed = True

    # Step 1: Install Playwright browsers
    print("\nStep 1: Installing Playwright browsers...")
    if not run_command(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Playwright browser installation"
    ):
        print("\nWarning: Playwright browser installation failed, but continuing...")

    # Step 2: Install dependencies if not already installed
    print("\nStep 2: Checking dependencies...")
    try:
        import playwright
        import pytest
        import websockets
        print("✓ All required dependencies are installed")
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Installing from requirements.txt...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Dependency installation"
        ):
            all_passed = False

    # Step 3: Run Playwright-based UI tests
    print("\nStep 3: Running Playwright UI tests...")
    ui_test_cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_web_ui.py",
        "-v",
        "--tb=short"
    ]
    if not run_command(ui_test_cmd, "Web UI tests"):
        all_passed = False

    # Step 4: Run WebSocket tests
    print("\nStep 4: Running WebSocket tests...")
    ws_test_cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_websocket.py",
        "-v",
        "--tb=short"
    ]
    if not run_command(ws_test_cmd, "WebSocket tests"):
        all_passed = False

    # Step 5: Run all tests together for coverage
    print("\nStep 5: Running all tests together...")
    all_tests_cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure for debugging
    ]
    if not run_command(all_tests_cmd, "All tests"):
        print("\nNote: Some tests failed. Review output above for details.")
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
