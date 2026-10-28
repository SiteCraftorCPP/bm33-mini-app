#!/usr/bin/env python3
"""Bump WEBAPP_CACHE_VERSION, rebuild web, restart API, refresh Telegram menu URL."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host_m = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
token_m = re.search(r"токен:\s*(\S+)", text, re.I)
domain_m = re.search(r"домен:\s*(\S+)", text, re.I)
if not host_m or not token_m or not domain_m:
    raise SystemExit("pas incomplete")

VERSION = "3"
domain = domain_m.group(1).strip()
token = token_m.group(1)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host_m.group(1), username="root", password=host_m.group(2), timeout=30)


def run(cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    return code, (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


cmds = f"""
set -e
cd /opt/bm33-mini-app
git fetch origin && git reset --hard origin/main
grep -q '^WEBAPP_CACHE_VERSION=' /etc/ches-hockey/env && \\
  sed -i 's/^WEBAPP_CACHE_VERSION=.*/WEBAPP_CACHE_VERSION={VERSION}/' /etc/ches-hockey/env || \\
  echo 'WEBAPP_CACHE_VERSION={VERSION}' >> /etc/ches-hockey/env
cd web
rm -rf dist
npm ci
VITE_MANAGER_USERNAME=Ches2424 VITE_BOT_USERNAME=chesalin_hockey_bot npm run build
nginx -t && systemctl reload nginx
systemctl restart ches-hockey-api
sleep 12
curl -sS --retry 5 --retry-delay 2 http://127.0.0.1:8000/api/health
"""

code, out = run(cmds)
print(out)
if code != 0:
    client.close()
    sys.exit(code)

launch_url = f"https://{domain}/?v={VERSION}"
menu_payload = json.dumps(
    {
        "menu_button": {
            "type": "web_app",
            "text": "🛒 Магазин",
            "web_app": {"url": launch_url},
        }
    }
).encode()
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/setChatMenuButton",
    data=menu_payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    print("setChatMenuButton:", resp.read().decode())

with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getChatMenuButton", timeout=30) as resp:
    print("getChatMenuButton:", resp.read().decode())

_, verify = run(
    f"curl -sS 'https://{domain}/?v={VERSION}' | grep -E 'index-|Chesalin' | head -3; "
    f"ls /opt/bm33-mini-app/web/dist/assets/*.js"
)
print(verify)
client.close()
print("DONE launch URL:", launch_url)
