#!/usr/bin/env python3
"""
Test CSS loading for both local and tunnel access
"""
import requests
import sys

def test_css_loading():
    """Test CSS file accessibility"""
    
    print("Testing CSS file loading...")
    print()
    
    # Test local CSS access
    print("1. Testing local CSS access...")
    try:
        response = requests.get("http://localhost:8801/style.css", timeout=5)
        if response.status_code == 200:
            print(f"✅ Local CSS loaded successfully ({len(response.text)} bytes)")
            print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        else:
            print(f"❌ Local CSS failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Local CSS failed: {e}")
    
    print()
    
    # Test tunnel CSS access
    print("2. Testing tunnel CSS access...")
    try:
        response = requests.get("https://code.andr.ca/telecli/style.css", timeout=10)
        if response.status_code == 200:
            print(f"✅ Tunnel CSS loaded successfully ({len(response.text)} bytes)")
            print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        else:
            print(f"❌ Tunnel CSS failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Tunnel CSS failed: {e}")
    
    print()
    
    # Test main page access
    print("3. Testing main page access...")
    try:
        response = requests.get("https://code.andr.ca/telecli/", timeout=10)
        if response.status_code == 200:
            print(f"✅ Tunnel main page loaded successfully")
            # Check if CSS link is present
            if 'main-stylesheet' in response.text:
                print("✅ Dynamic CSS link found in HTML")
            else:
                print("❌ Dynamic CSS link not found in HTML")
        else:
            print(f"❌ Tunnel main page failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Tunnel main page failed: {e}")

if __name__ == "__main__":
    test_css_loading()