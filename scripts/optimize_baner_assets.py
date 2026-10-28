#!/usr/bin/env python3
"""Copy images/baner.jpg → web/public + baner.jpg (1x) and baner@2x.jpg."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
MASTER = ROOT / "images" / "baner.jpg"
PUBLIC_SRC = PUBLIC / "baner.jpg"


def main() -> None:
    source = MASTER if MASTER.is_file() else PUBLIC_SRC
    if not source.is_file():
        raise SystemExit(f"Not found: {MASTER} or {PUBLIC_SRC}")

    if source != PUBLIC_SRC:
        shutil.copy2(source, PUBLIC_SRC)

    im = Image.open(PUBLIC_SRC).convert("RGB")
    w, h = im.size

    if w >= 1200:
        im.save(
            PUBLIC / "baner@2x.jpg",
            quality=92,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
        one_x = im.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
        one_x.save(
            PUBLIC / "baner.jpg",
            quality=90,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
    else:
        im.save(
            PUBLIC / "baner.jpg",
            quality=96,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
        im2 = im.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        im2.save(
            PUBLIC / "baner@2x.jpg",
            quality=92,
            optimize=True,
            progressive=True,
            subsampling=0,
        )

    logo = Image.open(PUBLIC / "logo-header.png").convert("RGBA")
    alpha = logo.split()[-1]
    bbox = alpha.getbbox()
    cropped = logo.crop(bbox) if bbox else logo
    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    ox = (side - cropped.size[0]) // 2
    oy = (side - cropped.size[1]) // 2
    square.paste(cropped, (ox, oy), cropped)
    for size, name in [(192, "home-screen-icon-192.png"), (512, "home-screen-icon-512.png")]:
        out = square.resize((size, size), Image.Resampling.LANCZOS)
        bg = Image.new("RGB", (size, size), "#0f2744")
        bg.paste(out, mask=out.split()[-1])
        bg.save(PUBLIC / name, optimize=True)

    print(f"baner master {w}x{h} → public baner.jpg + baner@2x.jpg")


if __name__ == "__main__":
    main()
