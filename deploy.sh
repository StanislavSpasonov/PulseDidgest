#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

git fetch origin
git checkout deploy
git pull --ff-only origin deploy

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip install -r requirements.txt

alembic upgrade head

sudo systemctl restart pulsedidgest
sudo systemctl status pulsedidgest --no-pager | head -n 20
