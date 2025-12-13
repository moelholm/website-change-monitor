# website-change-monitor

A GitHub Actions-powered service that monitors websites for changes using AWS DynamoDB for state tracking and creates GitHub issues when changes are detected.

## Features

- 🕐 **Automated Monitoring**: Runs every hour via GitHub Actions
- 🌐 **JavaScript Support**: Uses Playwright to render JavaScript-heavy pages
- 🔍 **Flexible Detection**: 
  - Checksum mode: Detect any content change
  - Pattern mode: Detect specific text appearing or disappearing
- 💾 **State Persistence**: AWS DynamoDB stores previous states
- 🔔 **Notifications**: Creates GitHub issues when changes are detected
- ☁️ **Secure AWS Integration**: OIDC authentication (no stored credentials)
- 🛠️ **Codespace Ready**: Pre-configured development environment

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
  # Checksum mode: Detects any content change
  - jobname: example-website
    url: https://example.com
  
  # Pattern mode: Detects when specific text appears or disappears
  - jobname: registration-check
    url: https://my.raceresult.com/365611/registration
    pattern: "100\\s+miles\\s+-\\s+waiting\\s+list\\s+0\\s+Available"
    action: when-text-disappears
```

**Required fields:**
- `jobname`: Unique identifier
- `url`: Website URL to monitor

**Pattern mode fields:**
- `pattern`: Regular expression to search for (HTML tags are stripped before matching)
- `action`: When to trigger an alert
  - `when-text-disappears` (default): Alert when pattern disappears
  - `when-text-appears`: Alert when pattern appears

### GitHub Secrets Setup

Configure secrets in your repository:

1. Navigate to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AWS_ROLE_ARN` | ARN of the IAM role for GitHub Actions | `arn:aws:iam::123456789012:role/GitHubActionsRole` |
| `AWS_REGION` | AWS region for DynamoDB | `us-east-1` |
| `DYNAMODB_TABLE_NAME` | (Optional) DynamoDB table name | `website-change-monitor` |

### Codespace Secrets (Optional)

For development in Codespaces:

1. Navigate to **User Settings** → **Codespaces** → **Secrets**
2. Add these secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AWS_SSO_PROFILE` | Your AWS SSO profile name | `codespace-sso` |
| `AWS_SSO_ACCOUNT` | Your AWS account ID | `123456789012` |
| `AWS_SSO_ROLE_NAME` | SSO role name | `AdministratorAccess` |
| `AWS_SSO_REGION` | AWS region | `us-east-1` |
| `AWS_SSO_START_URL` | AWS SSO start URL | `https://d-xxxxxxxxxx.awsapps.com/start` |

### AWS IAM Role Setup

#### Step 1: Create OIDC Provider in AWS

If you haven't already set up GitHub Actions OIDC provider in your AWS account:

1. Go to **IAM** → **Identity providers** → **Add provider**
2. Select **OpenID Connect**
3. Provider URL: `https://token.actions.githubusercontent.com`
4. Audience: `sts.amazonaws.com`
5. Click **Add provider**

#### Step 2: Create IAM Role

Create an IAM role with the following configuration:

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_USERNAME/website-change-monitor:*"
        }
      }
    }
  ]
}
```

**Permissions Policy:**
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

Replace `YOUR_ACCOUNT_ID` and `YOUR_GITHUB_USERNAME` with your actual values.

## Usage

### Automatic Monitoring

The workflow runs every hour automatically. To trigger manually:

1. Open the **Actions** tab
2. Select **Monitor Websites**
3. Click **Run workflow**

### Local Testing

```bash
pip install -r requirements.txt
aws configure  # or use AWS SSO
export DYNAMODB_TABLE_NAME=website-change-monitor
python monitor.py
```

## How It Works

1. **Load Configuration**: Read website jobs from `config.yml`
2. **Fetch Content**: Use Playwright to render the full page (including JavaScript)
3. **Detect Changes**:
   - **Checksum Mode**: Compute SHA-256 hash and compare with previous state
   - **Pattern Mode**: Strip HTML tags, search for regex pattern, and trigger alerts based on action:
     - `when-text-disappears`: Alert when pattern disappears
     - `when-text-appears`: Alert when pattern appears
4. **Compare State**: Check against stored state in DynamoDB
5. **Create Alert**: Generate GitHub issue for detected changes
6. **Update State**: Store new checksum/pattern state in DynamoDB

## Development

### Using GitHub Codespaces

This repository is pre-configured for GitHub Codespaces with Python 3.12, AWS CLI, and all dependencies.

After opening a Codespace, authenticate with AWS SSO:

```bash
aws sso login --profile codespace-sso
aws sts get-caller-identity --profile codespace-sso  # Verify
```

> **Note**: Configure [Codespace secrets](#codespace-secrets-optional) before opening the Codespace. The `AWS_SSO_ROLE_NAME` must match a role in your AWS IAM Identity Center.

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

## DynamoDB Schema

| Attribute | Type | Description |
|-----------|------|-------------|
| `jobname` | String (PK) | Unique job identifier |
| `url` | String | Website URL |
| `checksum` | String | SHA-256 hash of last content |
| `datetime` | String | ISO 8601 timestamp |
| `pattern_found` | Boolean | Pattern state (pattern mode only) |

## Troubleshooting

**Table creation fails**: Ensure IAM role has `dynamodb:CreateTable` permission.

**Authentication errors**: Verify OIDC provider, IAM trust policy, and repository secrets are configured correctly.

**No changes detected**: First run initializes state. Changes are detected on subsequent runs.

## License

MIT