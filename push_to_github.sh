#!/bin/bash

# Script to push poker-assistant to GitHub
echo "Setting up poker-assistant repository for GitHub..."

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Poker Assistant with BetOnline support

Features:
- Real-time hand history monitoring
- Player statistics tracking (VPIP, PFR, 3bet, etc.)
- BetOnline parser support
- HUD data extraction
- SQLite database for storing hands and stats
- Player profiling (TAG, LAG, FISH detection)
- Session tracking

Supported sites:
- BetOnline
- PokerStars
- GGPoker (basic support)"

# Create repository on GitHub (requires GitHub CLI)
echo ""
echo "Creating repository on GitHub..."
echo "If you have GitHub CLI installed, run:"
echo "  gh repo create poker-assistant --public --source=. --remote=origin --push"
echo ""
echo "Otherwise, manually:"
echo "1. Go to https://github.com/new"
echo "2. Create a new repository named 'poker-assistant'"
echo "3. Don't initialize with README (we already have one)"
echo "4. Then run these commands:"
echo ""
echo "  git remote add origin https://github.com/xuzinann/poker-assistant.git"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""
echo "Repository is ready to push!"