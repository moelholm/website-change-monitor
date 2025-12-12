#!/bin/bash

# Post-create commands for GitHub Codespaces
# This script runs after the codespace is created to set up dependencies

echo "🚀 Setting up website change monitor development environment..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install AWS CLI
echo "☁️ Installing AWS CLI..."

# Detect the OS and install AWS CLI accordingly
if grep -qi alpine /etc/os-release 2>/dev/null; then
    # Alpine Linux - install via pip (the glibc-based binary doesn't work on musl)
    echo "Detected Alpine Linux, installing AWS CLI via pip..."
    pip install awscli
else
    # Standard Linux with glibc - use the official installer
    echo "Installing AWS CLI via official installer..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws/
fi

echo "✅ Environment setup complete!"

echo "🔧 Generating AWS SSO configuration dynamically..."

# Expected externally provided env vars:
#   AWS_SSO_PROFILE      (e.g. codespace-sso)
#   AWS_SSO_ACCOUNT      (e.g. 123456789012)
#   AWS_SSO_ROLE_NAME    (e.g. MyRole)
#   AWS_SSO_REGION       (e.g. eu-north-1)
#   AWS_SSO_START_URL    (e.g. https://d-xxxxxx.awsapps.com/start)

missing=()
for v in AWS_SSO_PROFILE AWS_SSO_ACCOUNT AWS_SSO_REGION AWS_SSO_START_URL AWS_SSO_ROLE_NAME; do
	if [[ -z "${!v:-}" ]]; then
		missing+=("$v")
	fi
done

if (( ${#missing[@]} > 0 )); then
	echo "WARNING: Missing required SSO env vars: ${missing[*]} — ~/.aws/config will not be generated" >&2
else
	PROFILE_NAME="$AWS_SSO_PROFILE"
	ROLE_NAME="$AWS_SSO_ROLE_NAME"
	CONFIG_DIR="$HOME/.aws"
	mkdir -p "$CONFIG_DIR"
	CONFIG_FILE="$CONFIG_DIR/config"

	echo "Creating $CONFIG_FILE (profile $PROFILE_NAME)"
	{
		echo "[profile $PROFILE_NAME]"
		echo "sso_session = ${PROFILE_NAME}_session"
		echo "sso_account_id = $AWS_SSO_ACCOUNT"
		echo "sso_role_name = $ROLE_NAME"
		echo "region = $AWS_SSO_REGION"
		echo
		echo "[sso-session ${PROFILE_NAME}_session]"
		echo "sso_start_url = $AWS_SSO_START_URL"
		echo "sso_region = $AWS_SSO_REGION"
		echo "sso_registration_scopes = sso:account:access"
	} > "$CONFIG_FILE"

	chmod 600 "$CONFIG_FILE" || true
	echo "Wrote AWS SSO config to $CONFIG_FILE"

	# Set default profile and region for boto3/AWS CLI
	BASHRC="$HOME/.bashrc"
	echo "" >> "$BASHRC"
	echo "# AWS defaults for boto3 and AWS CLI" >> "$BASHRC"
	echo "export AWS_DEFAULT_PROFILE=$PROFILE_NAME" >> "$BASHRC"
	echo "export AWS_DEFAULT_REGION=$AWS_SSO_REGION" >> "$BASHRC"
	echo "export AWS_PROFILE=$PROFILE_NAME" >> "$BASHRC"
	echo "Added AWS_DEFAULT_PROFILE, AWS_PROFILE, and AWS_DEFAULT_REGION to $BASHRC"

fi
