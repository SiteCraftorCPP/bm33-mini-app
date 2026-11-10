#!/usr/bin/env python3
import re
from pathlib import Path

import paramiko

text = Path("pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
cmd = (
    "echo cache_count $(ls /var/lib/ches-hockey/catalog-images/*.bin 2>/dev/null | wc -l); "
    "find /var /opt /root /tmp -name '*11372408*' -o -name '*6d351e56*' 2>/dev/null | head -20"
)
_, stdout, stderr = client.exec_command(cmd, timeout=30)
stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
print(stderr.read().decode(errors="replace")[-300:])
client.close()
