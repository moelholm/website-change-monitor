# website-change-monitor

A GitHub Actions-powered service that monitors websites for changes using AWS DynamoDB for state tracking and creates GitHub issues when changes are detected.

## Features

- 🕐 **Automated Monitoring**: Runs every 6 hours via GitHub Actions
- 🔍 **Change Detection**: Uses MD5 checksums to detect content changes
- 💾 **State Persistence**: Stores checksums in AWS DynamoDB
- 🔔 **Notifications**: Creates GitHub issues when changes are detected
- ☁️ **AWS Integration**: Uses OIDC for secure AWS authentication
- 🛠️ **Codespace Ready**: Pre-configured development environment with AWS CLI

## Setup

### Prerequisites

1. **AWS Account** with:
   - DynamoDB access
   - OIDC identity provider configured for GitHub Actions
   - IAM role for GitHub Actions with DynamoDB permissions

2. **GitHub Repository Secrets**:
   - `AWS_ROLE_ARN`: ARN of the IAM role to assume
   - `AWS_REGION`: AWS region (e.g., `us-east-1`)
   - `DYNAMODB_TABLE_NAME`: (Optional) Name of the DynamoDB table (defaults to `website-change-monitor`)

3. **Codespace Secrets** (for development):
   - `AWS_SSO_PROFILE`: Your AWS SSO profile name
   - `AWS_SSO_ACCOUNT`: Your AWS account ID
   - `AWS_SSO_ROLE_NAME`: SSO role name
   - `AWS_SSO_REGION`: AWS region
   - `AWS_SSO_START_URL`: AWS SSO start URL

### Configuration

Edit `config.yml` to define websites to monitor:

```yaml
jobs:
  - jobname: example-website
    url: https://example.com
  
  - jobname: another-site
    url: https://another-site.com
```

Each job requires:
- `jobname`: Unique identifier for the monitoring job
- `url`: Full URL of the website to monitor

### AWS IAM Role Permissions

The IAM role used by GitHub Actions needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/website-change-monitor"
    }
  ]
}
```

## Usage

### Automatic Monitoring

The workflow runs automatically every 6 hours. You can also trigger it manually:

1. Go to **Actions** tab in your repository
2. Select **Monitor Websites** workflow
3. Click **Run workflow**

### Manual Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure  # or use AWS SSO

# Run the monitor
export DYNAMODB_TABLE_NAME=website-change-monitor
python monitor.py
```

## How It Works

1. **Configuration Loading**: Reads website jobs from `config.yml`
2. **Content Fetching**: Downloads each website's content
3. **Checksum Calculation**: Computes MD5 hash of the content
4. **State Comparison**: Compares with stored checksum in DynamoDB
5. **Change Detection**: If checksums differ, a change is detected
6. **Notification**: Creates a GitHub issue with change details
7. **State Update**: Updates DynamoDB with new checksum

## Development

### Using GitHub Codespaces

This repository is configured for GitHub Codespaces with:
- Python 3.12
- AWS CLI pre-installed
- Automatic AWS SSO configuration
- All required dependencies

Simply open the repository in a Codespace, and the environment will be set up automatically.

### Project Structure

```
.
├── .devcontainer/
│   ├── devcontainer.json          # Codespace configuration
│   └── postCreateCommand.sh       # Setup script for Codespace
├── .github/
│   └── workflows/
│       └── monitor-websites.yml   # GitHub Actions workflow
├── config.yml                      # Website monitoring configuration
├── monitor.py                      # Main monitoring script
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## DynamoDB Table Schema

The DynamoDB table stores the following attributes:

- `jobname` (String, Partition Key): Unique job identifier
- `url` (String): Website URL
- `checksum` (String): MD5 checksum of last known content
- `datetime` (String): ISO 8601 timestamp of last check

## Troubleshooting

### Table Creation Fails

Ensure your IAM role has `dynamodb:CreateTable` permission.

### Authentication Errors

Verify that:
- OIDC provider is correctly configured in AWS
- IAM role trust policy allows GitHub Actions
- Repository secrets are set correctly

### No Changes Detected

The first run initializes checksums. Changes are only detected on subsequent runs.

## License

MIT