#!/usr/bin/env python3
"""One-shot VPS deploy via SSH. Secrets only from local pas file (never commit)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAS_FILE = ROOT / "pas bm33 mini app.txt"
SA_LOCAL = Path(
    r"C:/Users/MOD PC COMPANY/.cursor/projects/c-Users-MOD-PC-COMPANY-Desktop-bm33-mini-app"
    r"/attachments/c3f25e2e-beb7-48e1-b17c-f442f7300d9d/tgbot-izyatia-e861a9cf8af4.json"
)
REMOTE_SA = "/etc/ches-hockey/google-service-account.json"
ENV_REMOTE = "/etc/ches-hockey/env"


def parse_pas(text: str) -> dict[str, str]:
    token = re.search(r"токен:\s*(\S+)", text, re.I)
    admins = re.search(r"админы:\s*([0-9;]+)", text, re.I)
    host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
    domain = re.search(r"домен:\s*(\S+)", text, re.I)
    manager = re.search(r"админы user name:\s*@?(\S+)", text, re.I)
    if not all([token, admins, host, domain]):
        raise SystemExit("Не удалось разобрать pas bm33 mini app.txt")
    return {
        "bot_token": token.group(1),
        "admin_ids": admins.group(1).replace(";", ","),
        "manager_username": manager.group(1) if manager else "",
        "host": host.group(1),
        "password": host.group(2),
        "domain": domain.group(1).strip(),
    }


def main() -> None:
    try:
        import paramiko
    except ImportError:
        raise SystemExit("pip install paramiko") from None

    cfg = parse_pas(PAS_FILE.read_text(encoding="utf-8"))
    if not SA_LOCAL.is_file():
        raise SystemExit(f"Service account JSON not found: {SA_LOCAL}")

    env_body = f"""APP_ENV=production
DATABASE_URL=sqlite:////var/lib/ches-hockey/ches_hockey.sqlite3
FRONTEND_URL=https://{cfg['domain']}
PUBLIC_WEBAPP_URL=https://{cfg['domain']}
DEMO_MODE=false
RUN_BOT=true
BOT_TOKEN={cfg['bot_token']}
ADMIN_IDS={cfg['admin_ids']}
SUPPORT_CHAT_ID=-1004387232874
MANAGER_TELEGRAM_USERNAME={cfg.get("manager_username", "")}
GOOGLE_SHEET_ID=1Jvgo--zRkIQsdl5X1JWGeGsRQybH1r2XO84955qrtPY
GOOGLE_SERVICE_ACCOUNT_FILE={REMOTE_SA}
SHEETS_SYNC_INTERVAL_SECONDS=60
"""

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["host"], username="root", password=cfg["password"], timeout=60)
    sftp = client.open_sftp()

    def run(cmd: str, timeout: int = 900) -> None:
        print(f"$ {cmd[:120]}...")
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        if out.strip():
            print(out[-4000:].encode("ascii", errors="replace").decode("ascii"))
        if exit_code != 0:
            print(err[-2000:].encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
            raise SystemExit(f"Command failed ({exit_code}): {cmd}")

    run("apt-get update -qq && apt-get install -y -qq git nginx certbot python3-certbot-nginx python3-venv curl")
    run(
        f"test -d /opt/bm33-mini-app/.git || git clone https://github.com/SiteCraftorCPP/bm33-mini-app.git /opt/bm33-mini-app"
    )
    run("cd /opt/bm33-mini-app && git fetch origin && git reset --hard origin/main")
    run("bash /opt/bm33-mini-app/deploy/bootstrap-server.sh", timeout=1200)

    with sftp.file(ENV_REMOTE, "w") as remote_env:
        remote_env.write(env_body)
    sftp.put(str(SA_LOCAL), REMOTE_SA)
    run(f"chmod 640 {ENV_REMOTE} {REMOTE_SA} && chown root:www-data {ENV_REMOTE} {REMOTE_SA}")
    run("systemctl restart ches-hockey-api && systemctl status ches-hockey-api --no-pager")

    sftp.close()
    client.close()
    print("Deploy finished:", cfg["domain"])


if __name__ == "__main__":
    main()
