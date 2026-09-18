#!/usr/bin/env bash
# Deploy / update the BoS portal on the Hostinger VPS.
#   sudo bash deploy/deploy.sh
set -euo pipefail

APP_DIR=/var/www/jain-bos-portal
SERVICE=jain-bos-portal

cd "$APP_DIR"

echo "→ pulling"
git pull --ff-only

echo "→ dependencies"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

echo "→ directories"
mkdir -p /var/log/$SERVICE "${UPLOAD_ROOT:-$APP_DIR/uploads}"
chown -R www-data:www-data /var/log/$SERVICE "${UPLOAD_ROOT:-$APP_DIR/uploads}" "$APP_DIR"

echo "→ restart"
systemctl daemon-reload
systemctl restart $SERVICE
sleep 2
systemctl --no-pager status $SERVICE | head -12

echo "→ health"
curl -fsS -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:8102/ || echo "  portal not responding"
echo "done"
