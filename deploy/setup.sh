#!/bin/bash
# Deploy Friday Golf to a Linux server (DigitalOcean droplet, Ubuntu)
# Run as root or with sudo

set -e

APP_DIR="/opt/friday-golf"

echo "=== Friday Golf Deployment ==="

# 1. Install system dependencies
echo "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip xvfb

# 2. Create app directory
echo "Setting up $APP_DIR..."
mkdir -p "$APP_DIR"

# 3. Copy project files (run this from the project directory)
echo "Copying project files..."
cp -r *.py requirements.txt templates/ "$APP_DIR/"
# Don't overwrite .env if it already exists
if [ ! -f "$APP_DIR/.env" ]; then
    cp .env "$APP_DIR/.env"
    echo "  Copied .env (edit credentials on the server!)"
else
    echo "  .env already exists, skipping"
fi

# Copy token.json if it exists (Gmail OAuth)
if [ -f token.json ]; then
    cp token.json "$APP_DIR/"
    echo "  Copied token.json"
fi

# Copy credentials.json if it exists
if [ -f credentials.json ]; then
    cp credentials.json "$APP_DIR/"
    echo "  Copied credentials.json"
fi

# 4. Set up Python virtual environment
echo "Setting up Python venv..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
playwright install chromium
playwright install-deps

# 5. Set up Xvfb for headed Chromium (Cloudflare bypass)
echo "Setting up Xvfb virtual display..."
cat > /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=Xvfb Virtual Display
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x1024x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xvfb
systemctl start xvfb

# 6. Install the Friday Golf service
echo "Installing systemd service..."
cp deploy/friday-golf.service /etc/systemd/system/ 2>/dev/null || \
    cp "$APP_DIR/../deploy/friday-golf.service" /etc/systemd/system/ 2>/dev/null || \
    echo "Copy friday-golf.service to /etc/systemd/system/ manually"

systemctl daemon-reload
systemctl enable friday-golf
systemctl start friday-golf

echo ""
echo "=== Done! ==="
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Useful commands:"
echo "  systemctl status friday-golf    # Check status"
echo "  journalctl -u friday-golf -f    # View logs"
echo "  systemctl restart friday-golf   # Restart"
