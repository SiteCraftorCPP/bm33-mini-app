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
cmds = """
mkdir -p /var/lib/ches-hockey/catalog-images
chown www-data:www-data /var/lib/ches-hockey/catalog-images
chmod 775 /var/lib/ches-hockey/catalog-images
systemctl restart ches-hockey-api
sleep 8
systemctl is-active ches-hockey-api
curl -sS --retry 5 --retry-delay 2 http://127.0.0.1:8000/api/health
"""
_, o, e = client.exec_command(cmds, timeout=120)
print(o.read().decode())
print(e.read().decode()[-800:])
client.close()
