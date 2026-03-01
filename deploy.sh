#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/Ingestion_Script_folder"
APP_DIR="$APP_ROOT/Ingestion_Script_1"
VENV_DIR="$APP_ROOT/.venv"
SERVICE_NAME="ingestion"

cd "$APP_DIR"

echo "Fetching latest code from origin/main..."
git fetch origin main
git reset --hard origin/main

echo "Installing/updating Python dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "Restarting service: $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "Deployment completed successfully."
