#!/usr/bin/env python3
"""
Test script for qBittorrent integration in ownfoil

This script tests:
1. QBittorrent connection
2. Adding a torrent via the API
3. The complete workflow from Jackett search to qBittorrent download
"""

import requests
import json
import sys

# Configuration
OWNFOIL_URL = "http://localhost:8465"
USERNAME = "admin"  # Update with your admin username
PASSWORD = "admin"  # Update with your admin password

# Test magnet link (Ubuntu 20.04 - safe test torrent)
TEST_MAGNET = "magnet:?xt=urn:btih:e2467cbf021192c241367b892230dc1e05c0580e&dn=ubuntu-20.04.3-desktop-amd64.iso"

def login():
    """Login to ownfoil and get session"""
    session = requests.Session()
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    response = session.post(f"{OWNFOIL_URL}/login", data=login_data)
    if response.status_code != 200 or "Login" in response.text:
        print("❌ Failed to login to ownfoil")
        return None
    
    print("✅ Successfully logged in to ownfoil")
    return session

def test_qbittorrent_connection(session):
    """Test qBittorrent connection"""
    response = session.post(
        f"{OWNFOIL_URL}/api/automation/test",
        json={"service": "qbittorrent"}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"✅ qBittorrent connection: {data.get('message')}")
            return True
        else:
            print(f"❌ qBittorrent connection failed: {data.get('message')}")
            return False
    else:
        print(f"❌ Failed to test qBittorrent connection: HTTP {response.status_code}")
        return False

def test_download_torrent(session):
    """Test downloading a torrent"""
    print("\n📥 Testing torrent download...")
    
    response = session.post(
        f"{OWNFOIL_URL}/api/automation/download",
        json={"magnet_link": TEST_MAGNET}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"✅ Torrent added: {data.get('message')}")
            return True
        else:
            print(f"❌ Failed to add torrent: {data.get('message')}")
            return False
    else:
        print(f"❌ Download API error: HTTP {response.status_code}")
        if response.text:
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"   Response: {response.text[:200]}")
        return False

def test_jackett_search(session):
    """Test Jackett search (if configured)"""
    print("\n🔍 Testing Jackett search...")
    
    # First check if Jackett is configured
    response = session.get(f"{OWNFOIL_URL}/api/settings/automation")
    if response.status_code != 200:
        print("⚠️  Could not check Jackett configuration")
        return
    
    config = response.json()
    if not config.get("success") or not config.get("automation", {}).get("jackett", {}).get("api_key"):
        print("ℹ️  Jackett API key not configured, skipping search test")
        return
    
    # Test search
    search_data = {
        "query": "Ubuntu",
        "type": "base",
        "title_id": ""
    }
    
    response = session.post(
        f"{OWNFOIL_URL}/api/jackett/search",
        json=search_data
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            results = data.get("results", [])
            print(f"✅ Jackett search successful: {len(results)} results found")
            if results:
                print(f"   First result: {results[0]['title'][:80]}...")
        else:
            print(f"❌ Jackett search failed: {data.get('message')}")
    else:
        print(f"❌ Jackett search API error: HTTP {response.status_code}")

def main():
    print("🧪 Testing qBittorrent Integration in Ownfoil")
    print("=" * 50)
    
    # Login
    session = login()
    if not session:
        return 1
    
    # Test qBittorrent connection
    print("\n🔌 Testing qBittorrent connection...")
    if not test_qbittorrent_connection(session):
        print("\n⚠️  Make sure qBittorrent is configured in Settings → Automation")
        return 1
    
    # Test Jackett search (optional)
    test_jackett_search(session)
    
    # Test downloading a torrent
    if test_download_torrent(session):
        print("\n✅ All tests passed! The integration is working correctly.")
        print("\n📝 Next steps:")
        print("1. Go to the Missing Content page (/missing)")
        print("2. Use Smart Search to find missing content")
        print("3. Click the download button to send torrents to qBittorrent")
        print("4. Check qBittorrent to see the downloads")
    else:
        print("\n❌ Some tests failed. Please check your configuration.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())