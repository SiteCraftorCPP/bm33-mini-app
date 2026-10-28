#!/usr/bin/env python3
"""Pull main and rebuild frontend on VPS."""
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

cmds = """
set -e
git config --global --add safe.directory /opt/bm33-mini-app
cd /opt/bm33-mini-app
git fetch origin
git reset --hard origin/main
cd web
npm ci
VITE_MANAGER_USERNAME=Ches2424 VITE_BOT_USERNAME=chesalin_hockey_bot npm run build
systemctl reload nginx
chown root:www-data /etc/ches-hockey
chmod 750 /etc/ches-hockey
chown root:www-data /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
chmod 640 /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
systemctl restart ches-hockey-api
sleep 8
systemctl is-active ches-hockey-api
curl -sS --retry 3 --retry-delay 2 http://127.0.0.1:8000/api/health
echo OK
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, stderr = client.exec_command(cmds, timeout=600)
code = stdout.channel.recv_exit_status()
out = (stdout.read() + stderr.read()).decode(errors="replace")
print(out.encode("ascii", errors="replace").decode("ascii"))
client.close()
raise SystemExit(code)
