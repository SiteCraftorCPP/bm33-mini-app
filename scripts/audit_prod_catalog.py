#!/usr/bin/env python3
"""Audit live catalog: sticks L/R, photos, proxy health."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from collections import Counter

BASE = "https://ches-hockey.ru"


def fetch_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=60) as resp:
        return json.load(resp)


def head_image(product_id: str) -> tuple[int, str, int]:
    url = f"{BASE}/api/catalog/image/{product_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read(1024)
            return resp.status, resp.headers.get("content-type", ""), len(data)
    except urllib.error.HTTPError as exc:
        body = exc.read(200).decode(errors="replace")
        return exc.code, body[:80], 0


def main() -> int:
    catalog = fetch_json("/api/catalog")
    products = catalog["products"]
    sticks = [p for p in products if p["category"] == "Клюшки"]

    issues: list[str] = []
    no_photo: list[str] = []
    bad_proxy: list[str] = []
    only_l: list[str] = []
    only_r: list[str] = []
    no_side: list[str] = []

    names = Counter(p["name"] for p in sticks)
    dup_names = [n for n, c in names.items() if c > 1]

    for p in sticks:
        sides = {v["side"] for v in p["variants"] if v.get("side")}
        if sides == {"L"}:
            only_l.append(p["name"])
        elif sides == {"R"}:
            only_r.append(p["name"])
        elif not sides:
            no_side.append(p["name"])

        if not p.get("imageUrl"):
            no_photo.append(p["name"])
            continue

        status, ctype, _ = head_image(p["id"])
        if status != 200 or not ctype.lower().startswith("image/"):
            bad_proxy.append(f"{p['name']} (HTTP {status}, {ctype})")

    if dup_names:
        issues.append(f"Дубликаты названий клюшек ({len(dup_names)}): {', '.join(dup_names[:8])}")
    if only_l:
        issues.append(f"Только L ({len(only_l)}): {', '.join(sorted(only_l)[:6])}…")
    if only_r:
        issues.append(f"Только R ({len(only_r)}): {', '.join(sorted(only_r)[:6])}…")
    if no_photo:
        issues.append(f"Без фото в API ({len(no_photo)}): {', '.join(sorted(no_photo)[:6])}…")
    if bad_proxy:
        issues.append(f"Прокси фото битый ({len(bad_proxy)}):")
        issues.extend(f"  - {x}" for x in bad_proxy[:15])

    print(f"Клюшек: {len(sticks)}, всего товаров: {len(products)}")
    print(f"Категории: { {c['name']: c['count'] for c in catalog['categories']} }")
    if issues:
        print("\n=== ПРОБЛЕМЫ ===")
        for line in issues:
            print(line)
    else:
        print("\nOK: дубликатов имён, односторонних хватов и битых прокси не найдено.")

    recharge = [p for p in sticks if "recharge" in p["name"].lower()]
    if recharge:
        p = recharge[0]
        st, ct, _ = head_image(p["id"])
        print(f"\nRecharge: {p['name']}, variants={len(p['variants'])}, sides={ {v['side'] for v in p['variants']} }, image HTTP {st} {ct}")

    return 1 if (bad_proxy or dup_names) else 0


if __name__ == "__main__":
    raise SystemExit(main())
