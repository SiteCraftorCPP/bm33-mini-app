#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/bm33-mini-app
ENV_FILE=/etc/ches-hockey/env
DOMAIN=ches-hockey.ru
REPO_URL="${REPO_URL:-https://github.com/SiteCraftorCPP/bm33-mini-app.git}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git nginx certbot python3-certbot-nginx python3-venv python3-pip curl

mkdir -p /etc/ches-hockey /var/lib/ches-hockey /var/lib/ches-hockey/catalog-images /var/www/certbot
chown root:www-data /etc/ches-hockey
chmod 750 /etc/ches-hockey

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  cd "$APP_DIR"
  git fetch origin
  git reset --hard origin/main
fi

cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -r backend/requirements.txt

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi

cd web
npm ci
VITE_BOT_USERNAME=chesalin_hockey_bot npm run build
cd "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Создайте $ENV_FILE из deploy/env.production.example и положите JSON service account в /etc/ches-hockey/"
  cp deploy/env.production.example "$ENV_FILE"
  chmod 640 "$ENV_FILE"
fi

cp deploy/ches-hockey-api.service /etc/systemd/system/ches-hockey-api.service
systemctl daemon-reload
systemctl enable ches-hockey-api

cp deploy/nginx-ches-hockey-http-only.conf /etc/nginx/sites-available/ches-hockey
ln -sf /etc/nginx/sites-available/ches-hockey /etc/nginx/sites-enabled/ches-hockey
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
  certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m admin@"$DOMAIN" || true
fi

if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
  cp deploy/nginx-ches-hockey.conf /etc/nginx/sites-available/ches-hockey
  ln -sf /etc/nginx/sites-available/ches-hockey /etc/nginx/sites-enabled/ches-hockey
else
  echo "SSL cert not ready — nginx stays on HTTP-only config"
fi
nginx -t && systemctl reload nginx

chown -R www-data:www-data "$APP_DIR" /var/lib/ches-hockey
systemctl restart ches-hockey-api || systemctl start ches-hockey-api

echo "Bootstrap done. Check: systemctl status ches-hockey-api"
