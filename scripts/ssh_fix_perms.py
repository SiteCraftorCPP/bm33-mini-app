#!/usr/bin/env python3
import re
from pathlib import Path
import paramiko

text = (Path(__file__).resolve().parents[1] / "pas bm33 mini app.txt").read_text(encoding="utf-8")
h = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
cmds = """
chown root:www-data /etc/ches-hockey
chmod 750 /etc/ches-hockey
chown root:www-data /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
chmod 640 /etc/ches-hockey/env /etc/ches-hockey/google-service-account.json
sudo -u www-data test -r /etc/ches-hockey/google-service-account.json && echo SA_OK
sudo -u www-data test -r /etc/ches-hockey/env && echo ENV_OK
systemctl restart ches-hockey-api
sleep 2
systemctl is-active ches-hockey-api
"""
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h.group(1), username="root", password=h.group(2), timeout=30)
_, o, e = c.exec_command(cmds, timeout=60)
print(o.channel.recv_exit_status())
print((o.read() + e.read()).decode(errors="replace"))
c.close()
