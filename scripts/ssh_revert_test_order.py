#!/usr/bin/env python3
"""Restore stock for a test order and reset status to new (run on VPS with env)."""
import asyncio
import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
order_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

remote_py = f"""
import asyncio
import sys
sys.path.insert(0, "/opt/bm33-mini-app/backend")
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.models import Order, OrderItem, Variant
from app.orders.stock import restore_accepted_order_stock

async def main():
    settings = get_settings()
    sheets = GoogleSheets(settings)
    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        order = db.get(Order, {order_id})
        if order is None:
            print("ORDER_NOT_FOUND")
            return
        items = db.scalars(select(OrderItem).where(OrderItem.order_id == {order_id})).all()
        for item in items:
            v = db.get(Variant, item.variant_id)
            print("BEFORE", item.variant_id, v.stock if v else None, item.quantity)
        if order.status == "accepted":
            await restore_accepted_order_stock(db, sheets, {order_id})
        order.status = "new"
        db.commit()
        for item in items:
            v = db.get(Variant, item.variant_id)
            print("AFTER", item.variant_id, v.stock if v else None)
    print("OK")

asyncio.run(main())
"""

text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
cmd = (
    "set -a && source /etc/ches-hockey/env && set +a && "
    f"/opt/bm33-mini-app/.venv/bin/python -c {repr(remote_py)}"
)
_, stdout, stderr = client.exec_command(cmd, timeout=120)
stdout.channel.recv_exit_status()
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
