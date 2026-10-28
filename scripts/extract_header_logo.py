#!/usr/bin/env python3
"""Crop header logo from images/shapka.pdf (logo in top-left of PDF page)."""
from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "images" / "shapka.pdf"
OUT = ROOT / "web" / "public" / "logo-header.png"


def main() -> None:
    if not PDF.is_file():
        raise SystemExit(f"Not found: {PDF}")
    doc = fitz.open(PDF)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            if px[x, y] < 245:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    inset = 14
    cropped = img.crop((min_x + inset, min_y + inset, max_x - inset, max_y - inset))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({cropped.size[0]}×{cropped.size[1]})")


if __name__ == "__main__":
    main()
