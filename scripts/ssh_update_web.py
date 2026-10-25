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
cd /opt/bm33-mini-app
git fetch origin
git reset --hard origin/main
cd web
npm ci
VITE_BOT_USERNAME=chesalin_hockey_bot npm run build
systemctl reload nginx
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
