#!/usr/bin/env python3
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
sftp = client.open_sftp()
sftp.put(
    str(ROOT / "deploy/nginx-ches-hockey.conf"),
    "/etc/nginx/sites-available/ches-hockey",
)
sftp.close()

cmds = """
set -e
ln -sf /etc/nginx/sites-available/ches-hockey /etc/nginx/sites-enabled/ches-hockey
rm -f /etc/nginx/sites-enabled/default
chown root:www-data /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
chmod 640 /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
nginx -t
systemctl reload nginx
ss -tlnp | grep -E ':80|:443' || true
systemctl restart ches-hockey-api
sleep 2
systemctl is-active nginx ches-hockey-api
curl -sS -o /dev/null -w 'http=%{http_code}\\n' http://127.0.0.1/
curl -sS -k -o /dev/null -w 'https=%{http_code}\\n' https://127.0.0.1/
"""
_, stdout, stderr = client.exec_command(cmds, timeout=120)
stdout.channel.recv_exit_status()
out = (stdout.read() + stderr.read()).decode(errors="replace")
print(out.encode("ascii", errors="replace").decode("ascii"))
client.close()
