# Roo Code Checkpoints - Configuration Guide

## Issue Identified

The Roo Code checkpoint feature was not working because the workspace was located at `/home/zihan/Desktop`, which is **explicitly forbidden** by Roo Code's checkpoint system.

### Forbidden Directories for Checkpoints

Roo Code's checkpoint system cannot be used in the following directories:
- Home directory (`~/`)
- Desktop (`~/Desktop`)
- Documents (`~/Documents`)
- Downloads (`~/Downloads`)

This restriction is built into the extension to prevent issues with the shadow git repository system.

## Solution Implemented

### 1. Created a Proper Project Directory

```bash
mkdir -p ~/projects/meat-quality-monitoring
```

### 2. Initialized a Git Repository

```bash
cd ~/projects/meat-quality-monitoring
git init
git config user.name "Roo Code"
git config user.email "noreply@example.com"
```

### 3. Created .gitignore

A `.gitignore` file was created to exclude unnecessary files:
- Python cache files (`__pycache__/`, `*.pyc`, etc.)
- Virtual environments (`venv/`, `env/`)
- IDE files (`.vscode/`, `.idea/`)
- OS files (`.DS_Store`, `Thumbs.db`)

### 4. Made Initial Commit

```bash
git add .
git commit -m "Initial commit - Meat Quality Monitoring project"
```

## How Roo Code Checkpoints Work

### Architecture

Roo Code uses a **shadow git repository** system for checkpoints:

1. **Shadow Git Repo**: Created in a separate directory (`~/.vscode-server/data/User/globalStorage/rooveterinaryinc.roo-cline/checkpoints/`)
2. **Worktree Configuration**: The shadow repo uses `core.worktree` to point to your workspace directory
3. **No .git in Workspace**: Your workspace doesn't need a `.git` folder - the shadow repo handles all version control

### Key Operations

#### Save Checkpoint
- Stages all files in the workspace
- Creates a commit with a descriptive message
- Stores the commit hash in the checkpoints list

#### Restore Checkpoint
- Performs `git clean -fd` to remove untracked files
- Performs `git reset --hard <commit>` to restore files
- Updates the checkpoints list

## Using Checkpoints

### Prerequisites

1. **Git must be installed** (already installed: `git version 2.47.3`)
2. **Workspace must NOT be in forbidden directories** (Desktop, Documents, Downloads, Home)
3. **No nested git repositories** in the workspace

### Enabling Checkpoints

When you open a Roo Code task in a valid workspace:
1. The checkpoint system automatically initializes
2. A shadow git repo is created if it doesn't exist
3. An initial base commit is created

### Creating Checkpoints

Roo Code automatically creates checkpoints at key points:
- Before making significant changes
- After completing tasks
- When you manually request a checkpoint

### Restoring Checkpoints

To restore a checkpoint:
1. Open the Roo Code webview
2. Navigate to the checkpoints section
3. Select the checkpoint you want to restore
4. Click the restore button

## Troubleshooting

### Checkpoints Not Working

1. **Check workspace location**: Ensure your project is not in Desktop, Documents, Downloads, or Home directory
2. **Check for nested git repos**: Run `find . -name ".git" -type d` to find nested repos
3. **Check Git installation**: Run `git --version` to verify Git is installed
4. **Check VS Code logs**: Look for checkpoint-related error messages

### Error Messages

- **"Cannot use checkpoints in {path}"**: Move your project to a different directory
- **"Checkpoints are disabled because a nested git repository was detected"**: Remove or relocate nested `.git` folders
- **"Git is required for the checkpoints feature"**: Install Git on your system

## Best Practices

1. **Use a dedicated projects directory**: `~/projects/` is a good location
2. **Initialize Git early**: Create a Git repo before starting work
3. **Use meaningful commit messages**: This helps identify checkpoints
4. **Regular checkpoints**: Roo Code creates checkpoints automatically, but you can also create them manually

## Project Location

The meat quality monitoring project has been moved to:
```
~/projects/meat-quality-monitoring/
```

### Running the Streamlit App

To run the Streamlit application:

```bash
cd ~/projects/meat-quality-monitoring
./venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Or to run in the background:

```bash
cd ~/projects/meat-quality-monitoring
nohup ./venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501 > /tmp/streamlit.log 2>&1 &
```

Access from your PC's browser:
```
http://0.0.0.0:8501
```

Or if accessing from the same machine:
```
http://localhost:8501
```

### Installing Dependencies (if needed)

```bash
cd ~/projects/meat-quality-monitoring
./venv/bin/pip install -r requirements.txt
```

## Verification

To verify the Git repository is properly configured:

```bash
cd ~/projects/meat-quality-monitoring
git status
git log --oneline
```

Expected output:
```
On branch master
nothing to commit, working tree clean
629911e Initial commit - Meat Quality Monitoring project
```

## Important Notes

### Virtual Environment Issue

When copying a project with a virtual environment from one location to another, the Python shebangs in the virtual environment's scripts will still point to the old location. This causes scripts like `streamlit` to fail.

**Solution**: Always recreate the virtual environment in the new location:

```bash
rm -rf venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Desktop Version

The original Desktop version still exists but:
- **No Git repository** (checkpoints won't work)
- **Forbidden directory** (Roo Code checkpoints disabled)
- **Old virtual environment** (shebangs point to wrong location)

**Recommendation**: Delete the Desktop version or rename it as a backup:

```bash
# To delete
rm -rf ~/Desktop/meat_quality_monitoring/

# Or to keep as backup
mv ~/Desktop/meat_quality_monitoring/ ~/Desktop/meat_quality_monitoring.backup/
```

Use the projects version (`~/projects/meat-quality-monitoring/`) for all future work with Roo Code checkpoints.
