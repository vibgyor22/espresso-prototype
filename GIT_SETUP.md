# Pushing Espresso to Git

## Prerequisites
1. Install Git: https://git-scm.com/download/win
2. Create a GitHub account: https://github.com

## Steps

### Step 1: Install Git
Download and install from https://git-scm.com/download/win

### Step 2: Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `espresso-prototype`
3. Description: "Advanced Statistical Analysis Platform with Web Interface"
4. Public or Private (your choice)
5. DO NOT initialize with README
6. Click "Create repository"

### Step 3: Configure Git (First Time Only)
```powershell
git config --global user.email "your.email@gmail.com"
git config --global user.name "Your Name"
```

### Step 4: Initialize Repository Locally
```powershell
cd C:\Users\vibho\Documents\espresso-prototype

# Initialize git
git init

# Add all files to staging
git add .

# Create initial commit
git commit -m "Initial commit: Espresso Phase 6 web interface with ARIMA and DiD analysis"
```

### Step 5: Add Remote and Push
```powershell
# Replace YOUR-USERNAME with your actual GitHub username
git remote add origin https://github.com/YOUR-USERNAME/espresso-prototype.git

# Rename branch to main (GitHub standard)
git branch -M main

# Push to GitHub
git push -u origin main
```

You'll be prompted for your GitHub username and password (or use a Personal Access Token).

## After Initial Push

For future changes:
```powershell
cd C:\Users\vibho\Documents\espresso-prototype

# Make your changes...

# Stage changes
git add .

# Commit
git commit -m "Description of what you changed"

# Push
git push
```

## View Repository Online
After pushing, visit: `https://github.com/YOUR-USERNAME/espresso-prototype`

## Useful Commands

```powershell
# Check status
git status

# See commit history
git log

# See what changed
git diff

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Clone (to download on another machine)
git clone https://github.com/YOUR-USERNAME/espresso-prototype.git
```

## Common Issues

**"Git not found"**: Install Git from https://git-scm.com/download/win and restart PowerShell

**"Permission denied"**: Use a GitHub Personal Access Token instead of password
- Create at: https://github.com/settings/tokens
- Click "Generate new token"
- Select `repo` scope
- Use token as password when prompted

**"Repository not empty"**: The `.gitignore` file ensures unnecessary files aren't committed
