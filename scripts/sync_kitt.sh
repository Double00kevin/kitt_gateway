#!/bin/bash
# MadProjx Sovereign Gateway - Automated Sync Script
# Navigate to the project root relative to script location
cd "$(dirname "$0")/.."

echo "--- Starting KITT Sync: $(date) ---"

# 1. Stage changes
git add .

# 2. Commit with timestamp
git commit -m "Automated Sync: $(date '+%Y-%m-%d %H:%M:%S')"

# 3. Push to Physical SSD
echo "Pushing to SSD Vault..."
git push ssd-vault master

# 4. Push to Cloud (GitHub)
echo "Pushing to GitHub Cloud..."
git push origin master

echo "--- Sync Complete! ---"
