#!/usr/bin/env python3
"""Sync ADMIN_IDS on VPS from pas bm33 mini app.txt (админы: line)."""
from __future__ import annotations

import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
admins = re.search(r"админы:\s*([0-9;]+)", text, re.I)
if not host or not admins:
    raise SystemExit("host or admins not found in pas file")

admin_ids = admins.group(1).replace(";", ",")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    stdout.channel.recv_exit_status()
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


print("=== before ===")
print(run("grep ^ADMIN_IDS= /etc/ches-hockey/env || true"))
run(
    f"grep -q '^ADMIN_IDS=' /etc/ches-hockey/env && "
    f"sed -i 's/^ADMIN_IDS=.*/ADMIN_IDS={admin_ids}/' /etc/ches-hockey/env || "
    f"echo 'ADMIN_IDS={admin_ids}' >> /etc/ches-hockey/env"
)
print("=== after ===")
print(run("grep ^ADMIN_IDS= /etc/ches-hockey/env"))
print(run("systemctl restart ches-hockey-api && sleep 2 && systemctl is-active ches-hockey-api"))
client.close()
