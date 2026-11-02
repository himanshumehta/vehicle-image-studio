#!/usr/bin/env python3
"""Build the before/after images used in README.md from real pipeline outputs.

Run the Quickstart demo first so out/ contains the processed files, then:

    python scripts/make_readme_images.py      # writes docs/images/*.jpg
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SAMPLES, OUT, DOCS = ROOT / "samples", ROOT / "out", ROOT / "docs" / "images"


def checkerboard(size, cell=24) -> Image.Image:
    w, h = size
    board = Image.new("RGB", size, (236, 236, 236))
    d = ImageDraw.Draw(board)
    for y in range(0, h, cell):
        for x in range((y // cell) % 2 * cell, w, cell * 2):
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(204, 204, 204))
    return board


def label(img: Image.Image, text: str) -> Image.Image:
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=max(16, img.width // 36))
    bbox = d.textbbox((0, 0), text, font=f)
    pad = 8
    d.rectangle([10, 10, 10 + bbox[2] - bbox[0] + 2 * pad, 10 + bbox[3] - bbox[1] + 2 * pad], fill=(20, 20, 24))
    d.text((10 + pad - bbox[0], 10 + pad - bbox[1]), text, font=f, fill=(255, 255, 255))
    return img


def side_by_side(left: Image.Image, right: Image.Image, gap=12) -> Image.Image:
    h = max(left.height, right.height)
    canvas = Image.new("RGB", (left.width + right.width + gap, h), (255, 255, 255))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))
    return canvas


def stack(rows, gap=12) -> Image.Image:
    w = max(r.width for r in rows)
    canvas = Image.new("RGB", (w, sum(r.height for r in rows) + gap * (len(rows) - 1)), (255, 255, 255))
    y = 0
    for r in rows:
        canvas.paste(r, (0, y))
        y += r.height + gap
    return canvas


def on_checkerboard(rgba: Image.Image) -> Image.Image:
    board = checkerboard(rgba.size).convert("RGBA")
    board.alpha_composite(rgba.convert("RGBA"))
    return board.convert("RGB")


def bg_removal_demo() -> Image.Image:
    rows = []
    for name in ("hatchback", "motorcycle"):
        before = Image.open(SAMPLES / f"{name}.jpg").convert("RGB").resize((720, 480), Image.LANCZOS)
        cut = Image.open(OUT / f"{name}-nobg.png").resize((720, 480), Image.LANCZOS)
        rows.append(side_by_side(label(before, "Before"), label(on_checkerboard(cut), "After: background removed")))
    return stack(rows)


def upscale_demo() -> Image.Image:
    small = Image.open(SAMPLES / "hatchback-small.jpg").convert("RGB")
    up = Image.open(OUT / "hatchback-small-4x.png").convert("RGB")
    box = (40, 115, 140, 185)  # plate + rear wheel region of the 320px input
    big_box = tuple(v * 4 for v in box)
    size = ((box[2] - box[0]) * 7, (box[3] - box[1]) * 7)
    naive = small.crop(box).resize(size, Image.BICUBIC)
    esr = up.crop(big_box).resize(size, Image.LANCZOS)
    return side_by_side(
        label(naive, f"Before: {small.width}x{small.height} input, bicubic zoom"),
        label(esr, f"After: Real-ESRGAN 4x ({up.width}x{up.height})"),
    )


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, img in (("demo-background-removal.jpg", bg_removal_demo()), ("demo-upscale.jpg", upscale_demo())):
        path = DOCS / name
        img.save(path, quality=85, optimize=True)
        print(path.relative_to(ROOT), img.size, f"{path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
