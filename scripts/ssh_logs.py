#!/usr/bin/env python3
import re
from pathlib import Path
import paramiko

text = (Path(__file__).resolve().parents[1] / "pas bm33 mini app.txt").read_text(encoding="utf-8")
h = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(h.group(1), username="root", password=h.group(2), timeout=30)
_, o, e = c.exec_command("journalctl -u ches-hockey-api -n 100 --no-pager", timeout=60)
o.channel.recv_exit_status()
print((o.read() + e.read()).decode(errors="replace"))
c.close()
