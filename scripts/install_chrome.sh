#!/bin/bash
set -e

echo "Updating packages and installing dependencies..."
sudo apt-get update && sudo apt-get install -y wget gnupg2 apt-utils --no-install-recommends

echo "Downloading Google Chrome..."
wget --no-check-certificate https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

echo "Installing Google Chrome..."
sudo dpkg -i google-chrome-stable_current_amd64.deb || true
sudo apt-get install -fy

echo "Cleaning up..."
sudo rm -rf /var/lib/apt/lists/* google-chrome-stable_current_amd64.deb

if which google-chrome-stable >/dev/null; then
    echo "✅ Google Chrome installed successfully!"
else
    echo "❌ Google Chrome installation failed."
    exit 1
fi
