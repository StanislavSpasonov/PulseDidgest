#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/stanislavspasonov/apps/PulseDidgest"
ENV_FILE="${APP_DIR}/.env"
VENV_DIR="${APP_DIR}/.venv"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Missing venv directory: $VENV_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

git fetch origin
git checkout deploy
git pull --ff-only origin deploy

"$VENV_DIR/bin/pip" install -r requirements.txt
"$VENV_DIR/bin/alembic" upgrade head

sudo cp ops/systemd/pulsedidgest.service /etc/systemd/system/pulsedidgest.service
sudo systemctl daemon-reload
sudo systemctl restart pulsedidgest
sudo systemctl --no-pager --full status pulsedidgest | head -n 30
