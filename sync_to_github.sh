#!/bin/bash
# Script to sync meat_quality_Air_data_ESP_Node to GitHub
# This script should be run from /home/zihan/projects directory

set -e

PROJECT_DIR="/home/zihan/projects/meat_quality_Air_data_ESP_Node"
GITHUB_REPO="git@github.com:ThZihan/meat_quality.git"
BRANCH="master"

# Create a temporary directory for git operations
TEMP_DIR="/tmp/meat_quality_git_$$"
mkdir -p "$TEMP_DIR"

echo "=== Syncing to GitHub ==="
echo "Project: $PROJECT_DIR"
echo "Branch: $BRANCH"
echo ""

# Initialize git repo in temp directory if it doesn't exist
if [ ! -d "$TEMP_DIR/.git" ]; then
    echo "Initializing git repository..."
    cd "$TEMP_DIR"
    git init
    git config user.name "Zihan"
    git config user.email "noreply@github.com"
    git remote add origin "$GITHUB_REPO"
    git fetch origin
    git checkout -b "$BRANCH" origin/"$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
fi

# Copy files from project to temp directory
echo "Copying files..."
rsync -av --delete --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
    --exclude='node_modules' --exclude='.venv' --exclude='venv' \
    --exclude='.DS_Store' \
    "$PROJECT_DIR/" "$TEMP_DIR/"

# Commit and push
cd "$TEMP_DIR"
echo "Checking git status..."
git add -A
if git diff --cached --quiet; then
    echo "No changes to commit."
else
    echo "Committing changes..."
    git commit -m "Update from workspace - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Pushing to GitHub..."
    git push origin "$BRANCH"
    echo "Successfully pushed to GitHub!"
fi

# Cleanup
cd /home/zihan/projects
rm -rf "$TEMP_DIR"

echo ""
echo "=== Sync complete ==="
