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
_, o, _ = client.exec_command("journalctl -u ches-hockey-api -n 40 --no-pager", timeout=30)
print(o.read().decode())
client.close()
