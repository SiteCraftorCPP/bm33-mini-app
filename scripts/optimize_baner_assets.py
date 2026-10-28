#!/usr/bin/env python3
"""Recompress baner + @2x/webp and home-screen icons from web/public sources."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
SRC = PUBLIC / "baner.jpg"


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Not found: {SRC}")
    im = Image.open(SRC).convert("RGB")
    w, h = im.size
    im2 = im.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    im.save(SRC, quality=94, optimize=True, progressive=True)
    im2.save(PUBLIC / "baner@2x.jpg", quality=92, optimize=True, progressive=True)
    im.save(PUBLIC / "baner.webp", quality=88, method=6)
    im2.save(PUBLIC / "baner@2x.webp", quality=85, method=6)

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
    print(f"baner {w}x{h} + derivatives ok")


if __name__ == "__main__":
    main()
