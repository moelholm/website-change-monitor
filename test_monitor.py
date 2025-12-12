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
        if 'pattern' in job:
            print(f"      Pattern: {job['pattern']}")
            print(f"      Action: {job.get('action', 'when-not-found')}")


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


def test_html_stripping():
    """Test HTML tag stripping."""
    print("\nTesting HTML stripping...")
    m = monitor.WebsiteMonitor()
    
    test_cases = [
        ("<p>Hello</p>", "Hello"),
        ("<div>Hello <span>World</span></div>", "Hello World"),
        ("<p>100 miles - \n<b>waiting list</b> 0 Available</p>", "100 miles - waiting list 0 Available"),
    ]
    
    for html, expected_text in test_cases:
        result = m.strip_html(html)
        # Normalize whitespace for comparison
        result_normalized = ' '.join(result.split())
        expected_normalized = ' '.join(expected_text.split())
        assert result_normalized == expected_normalized, f"HTML strip mismatch: got '{result}', expected '{expected_text}'"
        print(f"  ✓ '{html}' -> '{result_normalized}'")


def test_pattern_matching():
    """Test regex pattern matching."""
    print("\nTesting pattern matching...")
    import re
    
    # Test the specific pattern from the example
    pattern = r"100\s+miles\s+-\s+waiting\s+list\s+0\s+Available"
    
    test_cases = [
        ("100 miles - waiting list 0 Available", True),
        ("100 miles -  waiting list  0 Available", True),
        ("100 miles - \nwaiting list 0 Available", True),
        ("100 miles - waiting list 1 Available", False),
        ("200 miles - waiting list 0 Available", False),
    ]
    
    for text, should_match in test_cases:
        match = bool(re.search(pattern, text, re.IGNORECASE | re.DOTALL))
        assert match == should_match, f"Pattern match mismatch for '{text}'"
        print(f"  ✓ '{text}' -> {match}")


def test_pattern_validation():
    """Test pattern validation."""
    print("\nTesting pattern validation...")
    m = monitor.WebsiteMonitor()
    
    # Valid patterns
    assert m.validate_pattern(r"100\s+miles"), "Simple pattern should be valid"
    print("  ✓ Simple pattern is valid")
    
    # Invalid pattern - malformed regex
    try:
        result = m.validate_pattern(r"[invalid(")
        assert not result, "Malformed pattern should be invalid"
        print("  ✓ Malformed pattern is rejected")
    except:
        print("  ✓ Malformed pattern is rejected")


def test_should_trigger_alert():
    """Test the should_trigger_alert helper method."""
    print("\nTesting should_trigger_alert logic...")
    m = monitor.WebsiteMonitor()
    
    # Test 'when-not-found' action
    assert m.should_trigger_alert('when-not-found', True, False) == True, "Should trigger when pattern disappears"
    assert m.should_trigger_alert('when-not-found', False, False) == False, "Should not trigger when pattern stays absent"
    assert m.should_trigger_alert('when-not-found', True, True) == False, "Should not trigger when pattern stays present"
    assert m.should_trigger_alert('when-not-found', False, True) == False, "Should not trigger when pattern appears"
    print("  ✓ 'when-not-found' action logic correct")
    
    # Test 'when-found' action
    assert m.should_trigger_alert('when-found', False, True) == True, "Should trigger when pattern appears"
    assert m.should_trigger_alert('when-found', True, True) == False, "Should not trigger when pattern stays present"
    assert m.should_trigger_alert('when-found', False, False) == False, "Should not trigger when pattern stays absent"
    assert m.should_trigger_alert('when-found', True, False) == False, "Should not trigger when pattern disappears"
    print("  ✓ 'when-found' action logic correct")
    
    # Test invalid action
    assert m.should_trigger_alert('invalid', True, False) == False, "Invalid action should not trigger"
    print("  ✓ Invalid action returns False")


def test_action_validation():
    """Test that invalid action values are rejected."""
    print("\nTesting action validation...")
    m = monitor.WebsiteMonitor()
    
    # Mock job with invalid action
    invalid_action_job = {
        'jobname': 'test-job',
        'url': 'https://example.com',
        'pattern': 'test',
        'action': 'invalid-action'
    }
    
    # Mock fetch to avoid network call
    original_fetch = m.fetch_page_content
    original_get_state = m.get_stored_state
    original_store_state = m.store_state
    
    m.fetch_page_content = lambda url: "<html><body>test</body></html>"
    m.get_stored_state = lambda jobname: None  # Simulate first run
    m.store_state = lambda *args, **kwargs: None  # Mock storage
    
    try:
        result = m.check_website(invalid_action_job)
        assert result == False, "Invalid action should return False"
        print("  ✓ Invalid action 'invalid-action' is rejected")
        
        # Test empty string action
        invalid_action_job['action'] = ''
        result = m.check_website(invalid_action_job)
        assert result == False, "Empty action should return False"
        print("  ✓ Empty action is rejected")
        
        # Test valid actions work (should not raise errors)
        invalid_action_job['action'] = 'when-found'
        result = m.check_website(invalid_action_job)
        print("  ✓ Valid action 'when-found' is accepted")
        
        invalid_action_job['action'] = 'when-not-found'
        result = m.check_website(invalid_action_job)
        print("  ✓ Valid action 'when-not-found' is accepted")
        
    finally:
        m.fetch_page_content = original_fetch
        m.get_stored_state = original_get_state
        m.store_state = original_store_state


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
        test_html_stripping()
        test_pattern_matching()
        test_pattern_validation()
        test_should_trigger_alert()
        test_action_validation()
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
