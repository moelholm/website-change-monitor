#!/usr/bin/env python3
"""
Test script for the website monitor (without AWS dependencies)

This script tests the core functionality of the monitor without requiring
AWS credentials or DynamoDB access.
"""

import sys
import os

# Add current directory to path to import monitor module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import monitor


def test_config_loading():
    """Test configuration loading."""
    print("Testing configuration loading...")
    m = monitor.WebsiteMonitor()
    jobs = m.load_config()
    assert len(jobs) > 0, "Should load at least one job"
    assert all('jobname' in job and 'url' in job for job in jobs), "Jobs should have jobname and url"
    print(f"  ✓ Loaded {len(jobs)} job(s)")
    for job in jobs:
        print(f"    - {job['jobname']}: {job['url']}")


def test_checksum_calculation():
    """Test SHA-256 checksum calculation."""
    print("\nTesting checksum calculation...")
    m = monitor.WebsiteMonitor()
    
    # Test with known content
    test_cases = [
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("hello", "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"),
        ("test", "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"),
    ]
    
    for content, expected in test_cases:
        checksum = m.calculate_checksum(content)
        assert checksum == expected, f"Checksum mismatch for '{content}'"
        print(f"  ✓ '{content}' -> {checksum}")


def test_fetch_content():
    """Test content fetching (will fail without network, which is OK)."""
    print("\nTesting content fetching...")
    m = monitor.WebsiteMonitor()
    
    # This will likely fail in restricted environments, but we can test the interface
    content = m.fetch_page_content("https://example.com")
    if content:
        print(f"  ✓ Successfully fetched content ({len(content)} bytes)")
        checksum = m.calculate_checksum(content)
        print(f"  ✓ Content checksum: {checksum}")
    else:
        print("  ⚠️  Failed to fetch content (expected in restricted network environments)")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Website Monitor Test Suite")
    print("=" * 60)
    
    try:
        test_config_loading()
        test_checksum_calculation()
        test_fetch_content()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
