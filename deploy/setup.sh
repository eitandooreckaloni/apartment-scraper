#!/bin/bash
# Deployment setup script for Hostinger VPS (Ubuntu)

set -e

echo "=== Apartment Scraper Deployment Setup ==="

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
echo "Installing Python..."
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Playwright dependencies
echo "Installing Playwright system dependencies..."
sudo apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2

# Create app directory
APP_DIR="/opt/apartment-scraper"
echo "Setting up application in $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Copy files (assuming we're in the repo directory)
cp -r . $APP_DIR/
cd $APP_DIR

# Create virtual environment
echo "Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install firefox
playwright install-deps firefox

# Create data directory
mkdir -p data/session

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file - please edit with your credentials!"
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp deploy/apartment-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable apartment-scraper

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit /opt/apartment-scraper/.env with your credentials"
echo "2. Edit /opt/apartment-scraper/config.yaml with your criteria"
echo "3. Start the service: sudo systemctl start apartment-scraper"
echo "4. Check status: sudo systemctl status apartment-scraper"
echo "5. View logs: journalctl -u apartment-scraper -f"
