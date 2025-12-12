#!/usr/bin/env python3
"""
Website Change Monitor Script

This script monitors websites for changes by:
1. Reading job configurations from config.yml
2. Fetching website content and calculating MD5 checksums
3. Storing/comparing checksums in DynamoDB
4. Creating GitHub issues when changes are detected
"""

import hashlib
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import requests
import yaml
from botocore.exceptions import ClientError


class WebsiteMonitor:
    """Monitor websites for changes using DynamoDB for state tracking."""

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

    def load_config(self) -> List[Dict[str, str]]:
        """Load job configurations from YAML file.
        
        Returns:
            List of job configurations with jobname and url
        """
        try:
            with open(self.config_file, 'r') as f:
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
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def calculate_checksum(self, content: str) -> str:
        """Calculate MD5 checksum of content.
        
        Args:
            content: String content to checksum
            
        Returns:
            MD5 checksum as hexadecimal string
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def get_stored_checksum(self, jobname: str) -> Optional[Dict]:
        """Retrieve stored checksum from DynamoDB.
        
        Args:
            jobname: Job identifier
            
        Returns:
            Item dict with checksum and datetime, or None if not found
        """
        self._ensure_dynamodb_connection()
        try:
            response = self.table.get_item(Key={'jobname': jobname})
            return response.get('Item')
        except ClientError as e:
            print(f"Error retrieving checksum for {jobname}: {e}")
            return None

    def store_checksum(self, jobname: str, url: str, checksum: str):
        """Store checksum in DynamoDB.
        
        Args:
            jobname: Job identifier
            url: URL being monitored
            checksum: MD5 checksum of the content
        """
        self._ensure_dynamodb_connection()
        try:
            self.table.put_item(
                Item={
                    'jobname': jobname,
                    'url': url,
                    'checksum': checksum,
                    'datetime': datetime.utcnow().isoformat()
                }
            )
        except ClientError as e:
            print(f"Error storing checksum for {jobname}: {e}")

    def check_website(self, job: Dict[str, str]) -> bool:
        """Check a single website for changes.
        
        Args:
            job: Job configuration with jobname and url
            
        Returns:
            True if change detected, False otherwise
        """
        jobname = job['jobname']
        url = job['url']
        
        print(f"Checking {jobname} ({url})...")
        
        # Fetch current content
        content = self.fetch_page_content(url)
        if content is None:
            print(f"  ⚠️  Failed to fetch content for {jobname}")
            return False
        
        # Calculate checksum
        current_checksum = self.calculate_checksum(content)
        
        # Get stored checksum
        stored_item = self.get_stored_checksum(jobname)
        
        if stored_item is None:
            # First time monitoring this website
            print(f"  ℹ️  First check for {jobname}, storing initial checksum")
            self.store_checksum(jobname, url, current_checksum)
            return False
        
        stored_checksum = stored_item.get('checksum')
        
        if current_checksum != stored_checksum:
            # Change detected!
            print(f"  🔔 CHANGE DETECTED for {jobname}!")
            print(f"     Old checksum: {stored_checksum}")
            print(f"     New checksum: {current_checksum}")
            
            # Update stored checksum
            self.store_checksum(jobname, url, current_checksum)
            
            # Record change
            self.changes_detected.append({
                'jobname': jobname,
                'url': url,
                'old_checksum': stored_checksum,
                'new_checksum': current_checksum,
                'detected_at': datetime.utcnow().isoformat()
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
        
        with open(summary_file, 'a') as f:
            f.write("# Website Change Monitor Results\n\n")
            
            if self.changes_detected:
                f.write(f"## 🔔 {len(self.changes_detected)} Change(s) Detected\n\n")
                for change in self.changes_detected:
                    f.write(f"### {change['jobname']}\n")
                    f.write(f"- **URL**: {change['url']}\n")
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
            with open(output_file, 'a') as f:
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
