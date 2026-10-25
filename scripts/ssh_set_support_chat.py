#!/usr/bin/env python3
"""Set SUPPORT_CHAT_ID on VPS and send a Telegram test message."""
import base64
import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
CHAT_ID = sys.argv[1] if len(sys.argv) > 1 else "-1004387232874"

text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
if not host:
    raise SystemExit("host not found in pas file")
cfg = {"host": host.group(1), "password": host.group(2)}

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(cfg["host"], username="root", password=cfg["password"], timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    stdout.channel.recv_exit_status()
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


print("=== before ===")
print(run("grep -E 'SUPPORT_CHAT|RUN_BOT' /etc/ches-hockey/env || true"))

run(
    f"grep -q '^SUPPORT_CHAT_ID=' /etc/ches-hockey/env && "
    f"sed -i 's/^SUPPORT_CHAT_ID=.*/SUPPORT_CHAT_ID={CHAT_ID}/' /etc/ches-hockey/env || "
    f"echo 'SUPPORT_CHAT_ID={CHAT_ID}' >> /etc/ches-hockey/env"
)

print("=== after ===")
print(run("grep SUPPORT_CHAT /etc/ches-hockey/env"))
print(run("systemctl restart ches-hockey-api && sleep 2 && systemctl is-active ches-hockey-api"))

test_py = """
import json
import urllib.error
import urllib.request
from pathlib import Path

env = {}
for line in Path('/etc/ches-hockey/env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()
token = env.get('BOT_TOKEN', '')
chat = env.get('SUPPORT_CHAT_ID', '')
if not token:
    raise SystemExit('NO_TOKEN')
url = f'https://api.telegram.org/bot{token}/sendMessage'
payload = {
    'chat_id': int(chat),
    'text': 'Ches Hockey: тест чата менеджеров. Новые заказы с кнопками «Принять» / «Связались» идут сюда.',
}
body = json.dumps(payload).encode()
req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print('SEND_OK', data.get('ok'), 'message_id', data.get('result', {}).get('message_id'))
except urllib.error.HTTPError as exc:
    print('SEND_FAIL', exc.code, exc.read().decode()[:800])
"""
b64 = base64.b64encode(test_py.encode()).decode()
print(run(f"echo {b64} | base64 -d | python3"))

# getChat sanity check
get_chat_py = """
import json, urllib.request
from pathlib import Path
env = {}
for line in Path('/etc/ches-hockey/env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1); env[k.strip()]=v.strip()
token, chat = env['BOT_TOKEN'], env['SUPPORT_CHAT_ID']
url = f"https://api.telegram.org/bot{token}/getChat?chat_id={chat}"
with urllib.request.urlopen(url, timeout=20) as r:
    d=json.loads(r.read().decode())
r=d.get('result',{})
print('CHAT', r.get('type'), r.get('title') or r.get('username'))
"""
b64g = base64.b64encode(get_chat_py.encode()).decode()
print(run(f"echo {b64g} | base64 -d | python3"))

client.close()
