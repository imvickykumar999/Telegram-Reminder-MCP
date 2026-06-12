#!/bin/bash

# Exit on error
set -e

# Usage helper
show_help() {
    echo "Usage: ./deploy.sh [commit_message]"
    echo ""
    echo "To push using a GitHub token securely without saving it in the repository:"
    echo "  GITHUB_TOKEN=your_token_here ./deploy.sh \"your commit message\""
}

if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_help
    exit 0
fi

# Get commit message from argument, or default
COMMIT_MSG="${1:-Update changes}"

# Stage all files
echo "Staging files..."
git add .

# Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "No changes detected to commit."
else
    echo "Committing changes with message: \"$COMMIT_MSG\""
    git commit -m "$COMMIT_MSG"
fi

# Determine remote URL
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

if [ -z "$REMOTE_URL" ]; then
    echo "Error: No remote repository configured for 'origin'."
    exit 1
fi

# Push changes
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Token detected. Preparing secure remote URL..."
    # Strip existing credentials if any
    CLEAN_URL=$(echo "$REMOTE_URL" | sed -E 's/https:\/\/[^@]+@/https:\/\//')
    # Inject token
    AUTH_URL=$(echo "$CLEAN_URL" | sed -E "s|https://|https://$GITHUB_TOKEN@|")
    
    # Set auth URL, push, and revert back to clean URL to keep local config clean
    git remote set-url origin "$AUTH_URL"
    
    echo "Pushing changes to origin main..."
    if git push origin main; then
        echo "Push successful."
    else
        echo "Error: Push failed."
        git remote set-url origin "$CLEAN_URL"
        exit 1
    fi
    
    # Clean up local git remote URL configuration
    git remote set-url origin "$CLEAN_URL"
else
    echo "No GITHUB_TOKEN environment variable found."
    echo "Pushing using standard git remote config..."
    git push origin main
fi

echo "Deploy finished successfully!"
