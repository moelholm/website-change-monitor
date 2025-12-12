#!/usr/bin/env python3
"""
Website Change Monitor Script

This script monitors websites for changes by:
1. Reading job configurations from config.yml
2. Fetching website content and calculating SHA-256 checksums
3. Storing/comparing checksums in DynamoDB
4. Creating GitHub issues when changes are detected
"""

import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
import requests
import yaml
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup


class WebsiteMonitor:
    """Monitor websites for changes using DynamoDB for state tracking."""

    # Pattern validation constants
    MAX_PATTERN_LENGTH = 500
    MAX_REPETITION_OPERATORS = 10

    def __init__(self, config_file: str = "config.yml", table_name: str = "website-change-monitor"):
        """Initialize the website monitor.
        
        Args:
            config_file: Path to the YAML configuration file
            table_name: Name of the DynamoDB table for state storage
        """
        self.config_file = config_file
        self.table_name = table_name
        self.dynamodb = None
        self.table = None
        self.changes_detected = []
    
    def _ensure_dynamodb_connection(self):
        """Ensure DynamoDB connection is established."""
        if self.dynamodb is None:
            self.dynamodb = boto3.resource('dynamodb')
            self.table = self.dynamodb.Table(self.table_name)

    def load_config(self) -> List[Dict[str, Any]]:
        """Load job configurations from YAML file.
        
        Returns:
            List of job configurations with jobname, url, and optional pattern/action
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('jobs', [])
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_file}' not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing configuration file: {e}")
            sys.exit(1)

    def fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch the content of a webpage.
        
        Args:
            url: URL of the webpage to fetch
            
        Returns:
            Page content as string, or None if fetch failed
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; WebsiteChangeMonitor/1.0; +https://github.com/moelholm/website-change-monitor)'
            }
            response = requests.get(url, timeout=30, headers=headers, verify=True)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of content.
        
        Args:
            content: String content to checksum
            
        Returns:
            SHA-256 checksum as hexadecimal string
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def strip_html(self, content: str) -> str:
        """Strip HTML tags from content for cleaner text matching.
        
        Args:
            content: HTML content
            
        Returns:
            Plain text content with HTML tags removed
        """
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)

    def get_stored_state(self, jobname: str) -> Optional[Dict]:
        """Retrieve stored state from DynamoDB.
        
        Args:
            jobname: Job identifier
            
        Returns:
            Item dict with checksum, url, datetime, and optional pattern_found, or None if not found
        """
        self._ensure_dynamodb_connection()
        try:
            response = self.table.get_item(Key={'jobname': jobname})
            return response.get('Item')
        except ClientError as e:
            print(f"Error retrieving state for {jobname}: {e}")
            return None

    def store_state(self, jobname: str, url: str, checksum: str, pattern_found: Optional[bool] = None):
        """Store monitoring state in DynamoDB.
        
        Args:
            jobname: Job identifier
            url: URL being monitored
            checksum: SHA-256 checksum of the content
            pattern_found: Optional boolean indicating if pattern was found (for pattern-based monitoring)
        """
        self._ensure_dynamodb_connection()
        try:
            item = {
                'jobname': jobname,
                'url': url,
                'checksum': checksum,
                'datetime': datetime.now(timezone.utc).isoformat()
            }
            if pattern_found is not None:
                item['pattern_found'] = pattern_found
            self.table.put_item(Item=item)
        except ClientError as e:
            print(f"Error storing state for {jobname}: {e}")

    def validate_pattern(self, pattern: str) -> bool:
        """Validate a regex pattern for safety.
        
        Args:
            pattern: Regular expression pattern to validate
            
        Returns:
            True if pattern is valid and safe
        """
        try:
            # Try to compile the pattern
            re.compile(pattern)
            
            # Prevent overly complex patterns
            if len(pattern) > self.MAX_PATTERN_LENGTH:
                print(f"  ⚠️  Warning: Pattern is too long (>{self.MAX_PATTERN_LENGTH} chars)")
                return False
            
            # Basic checks for potentially dangerous patterns
            # Prevent excessive repetition patterns that could cause ReDoS
            if pattern.count('*') > self.MAX_REPETITION_OPERATORS or pattern.count('+') > self.MAX_REPETITION_OPERATORS:
                print(f"  ⚠️  Warning: Pattern contains many repetition operators")
                return False
            
            # Check for nested quantifiers which are classic ReDoS patterns
            # Patterns like (a+)+, (a*)*, (a*)+, (a+)* are dangerous
            nested_quantifier_patterns = [
                r'\([^)]*\+\)\+',  # (x+)+
                r'\([^)]*\*\)\*',  # (x*)*
                r'\([^)]*\*\)\+',  # (x*)+
                r'\([^)]*\+\)\*',  # (x+)*
            ]
            for dangerous_pattern in nested_quantifier_patterns:
                if re.search(dangerous_pattern, pattern):
                    print(f"  ⚠️  Warning: Pattern contains nested quantifiers (potential ReDoS)")
                    return False
                
            return True
        except re.error as e:
            print(f"  ⚠️  Invalid regex pattern: {e}")
            return False

    def check_website(self, job: Dict[str, Any]) -> bool:
        """Check a single website for changes.
        
        Args:
            job: Job configuration with jobname, url, and optional pattern/action
            
        Returns:
            True if change detected, False otherwise
        """
        jobname = job['jobname']
        url = job['url']
        pattern = job.get('pattern')
        action = job.get('action', 'when-not-found')
        valid_actions = {'when-found', 'when-not-found'}
        if action not in valid_actions:
            print(f"  ⚠️  Invalid action '{action}' for job '{jobname}'. Must be one of {valid_actions}. Skipping job.")
            return False
        
        print(f"Checking {jobname} ({url})...")
        if pattern:
            print(f"  Pattern: {pattern}")
            print(f"  Action: {action}")
            
            # Validate pattern before using it
            if not self.validate_pattern(pattern):
                print(f"  ⚠️  Skipping pattern check due to invalid pattern")
                pattern = None
        
        # Fetch current content
        content = self.fetch_page_content(url)
        if content is None:
            print(f"  ⚠️  Failed to fetch content for {jobname}")
            return False
        
        # Calculate checksum
        current_checksum = self.calculate_checksum(content)
        
        # Get stored state
        stored_item = self.get_stored_state(jobname)
        
        # Pattern-based monitoring
        if pattern:
            # Strip HTML for cleaner matching
            plain_text = self.strip_html(content)
            
            # Check if pattern matches
            pattern_found = bool(re.search(pattern, plain_text, re.IGNORECASE | re.DOTALL))
            
            if stored_item is None:
                # First time monitoring this website
                print(f"  ℹ️  First check for {jobname}, pattern {'found' if pattern_found else 'not found'}")
                self.store_state(jobname, url, current_checksum, pattern_found)
                return False
            
            stored_pattern_found = stored_item.get('pattern_found', False)
            
            # Determine if we should trigger based on action
            change_detected = False
            if action == 'when-not-found' and stored_pattern_found and not pattern_found:
                # Pattern was found before but is not found now
                print(f"  🔔 CHANGE DETECTED: Pattern no longer found!")
                change_detected = True
            elif action == 'when-found' and not stored_pattern_found and pattern_found:
                # Pattern was not found before but is found now
                print(f"  🔔 CHANGE DETECTED: Pattern now found!")
                change_detected = True
            else:
                print(f"  ✅ No relevant change: pattern is {'found' if pattern_found else 'not found'}")
            
            # Update stored state
            self.store_state(jobname, url, current_checksum, pattern_found)
            
            if change_detected:
                # Record change
                self.changes_detected.append({
                    'jobname': jobname,
                    'url': url,
                    'pattern': pattern,
                    'action': action,
                    'pattern_found': pattern_found,
                    'detected_at': datetime.now(timezone.utc).isoformat()
                })
                return True
            
            return False
        
        # Checksum-based monitoring (original behavior)
        if stored_item is None:
            # First time monitoring this website
            print(f"  ℹ️  First check for {jobname}, storing initial checksum")
            self.store_state(jobname, url, current_checksum)
            return False
        
        stored_checksum = stored_item.get('checksum')
        
        if current_checksum != stored_checksum:
            # Change detected!
            print(f"  🔔 CHANGE DETECTED for {jobname}!")
            print(f"     Old checksum: {stored_checksum}")
            print(f"     New checksum: {current_checksum}")
            
            # Update stored checksum
            self.store_state(jobname, url, current_checksum)
            
            # Record change
            self.changes_detected.append({
                'jobname': jobname,
                'url': url,
                'old_checksum': stored_checksum,
                'new_checksum': current_checksum,
                'detected_at': datetime.now(timezone.utc).isoformat()
            })
            
            return True
        else:
            print(f"  ✅ No change detected for {jobname}")
            return False

    def create_summary_output(self):
        """Create GitHub Actions step summary with results."""
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
        if not summary_file:
            return
        
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write("# Website Change Monitor Results\n\n")
            
            if self.changes_detected:
                f.write(f"## 🔔 {len(self.changes_detected)} Change(s) Detected\n\n")
                for change in self.changes_detected:
                    f.write(f"### {change['jobname']}\n")
                    f.write(f"- **URL**: {change['url']}\n")
                    
                    # Pattern-based change
                    if 'pattern' in change:
                        f.write(f"- **Pattern**: `{change['pattern']}`\n")
                        f.write(f"- **Action**: {change['action']}\n")
                        f.write(f"- **Pattern Found**: {change['pattern_found']}\n")
                    # Checksum-based change
                    else:
                        f.write(f"- **Old Checksum**: `{change['old_checksum']}`\n")
                        f.write(f"- **New Checksum**: `{change['new_checksum']}`\n")
                    
                    f.write(f"- **Detected At**: {change['detected_at']}\n\n")
            else:
                f.write("## ✅ No Changes Detected\n\n")
                f.write("All monitored websites remain unchanged.\n")

    def set_output(self, name: str, value: str):
        """Set GitHub Actions output variable."""
        output_file = os.environ.get('GITHUB_OUTPUT')
        if output_file:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"{name}={value}\n")

    def run(self):
        """Run the monitoring process for all configured jobs."""
        print("=" * 60)
        print("Website Change Monitor")
        print("=" * 60)
        
        # Load configuration
        jobs = self.load_config()
        print(f"\nLoaded {len(jobs)} job(s) from configuration\n")
        
        # Check each website
        for job in jobs:
            self.check_website(job)
            print()
        
        # Create summary
        self.create_summary_output()
        
        # Set outputs for GitHub Actions
        changes_count = len(self.changes_detected)
        self.set_output('changes_detected', str(changes_count))
        self.set_output('has_changes', 'true' if changes_count > 0 else 'false')
        
        # Final summary
        print("=" * 60)
        if self.changes_detected:
            print(f"✨ Monitoring complete: {changes_count} change(s) detected")
        else:
            print("✨ Monitoring complete: No changes detected")
        print("=" * 60)
        
        return 0 if changes_count == 0 else 1


def main():
    """Main entry point."""
    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'website-change-monitor')
    monitor = WebsiteMonitor(table_name=table_name)
    sys.exit(monitor.run())


if __name__ == '__main__':
    main()
