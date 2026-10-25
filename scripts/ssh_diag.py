#!/usr/bin/env python3
import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
cfg = {}
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
cfg["host"], cfg["password"] = host.group(1), host.group(2)

cmds = [
    "ss -tlnp | grep -E ':80|:443|:8000' || true",
    "systemctl is-active nginx ches-hockey-api",
    "nginx -t 2>&1",
    "ufw status 2>/dev/null || true",
    "iptables -L INPUT -n 2>/dev/null | head -15 || true",
    "curl -sS -o /dev/null -w 'local_http=%{http_code}\\n' http://127.0.0.1/",
    "curl -sS -o /dev/null -w 'local_api=%{http_code}\\n' http://127.0.0.1:8000/api/health",
    "journalctl -u nginx -n 5 --no-pager 2>&1",
    "journalctl -u ches-hockey-api -n 8 --no-pager 2>&1",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(cfg["host"], username="root", password=cfg["password"], timeout=30)
for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    stdout.channel.recv_exit_status()
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    print(out.encode("ascii", errors="replace").decode("ascii"))
client.close()
