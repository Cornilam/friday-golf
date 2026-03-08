#!/bin/bash
# Quick deploy: rsync files to your droplet and restart the service
# Usage: bash deploy/push.sh <droplet-ip>
#   e.g. bash deploy/push.sh 164.90.xxx.xxx

set -e

if [ -z "$1" ]; then
    echo "Usage: bash deploy/push.sh <droplet-ip-or-hostname>"
    exit 1
fi

SERVER="$1"
APP_DIR="/opt/friday-golf"

echo "Deploying to $SERVER..."

# Sync project files (exclude local-only files)
rsync -avz --exclude '.env' \
    --exclude 'friday_golf.db' \
    --exclude 'token.json' \
    --exclude '__pycache__' \
    --exclude 'venv' \
    --exclude '.claude' \
    --exclude 'deploy' \
    ./ "root@$SERVER:$APP_DIR/"

# Copy deploy scripts
rsync -avz deploy/ "root@$SERVER:$APP_DIR/deploy/"

echo "Files synced. Restarting service..."
ssh "root@$SERVER" "cd $APP_DIR && source venv/bin/activate && pip install -q -r requirements.txt && systemctl restart friday-golf"

echo "Done! Dashboard: http://$SERVER:5000"
