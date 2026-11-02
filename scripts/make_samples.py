#!/usr/bin/env python3
"""Generate the synthetic sample images in samples/.

The samples are drawn procedurally with Pillow (no photographs, no third-party
assets), so they can be redistributed with the MIT-licensed code. Each one has
a busy background, a fake number plate and a semi-transparent watermark, so the
background-removal, upscaling and plate/watermark clean-up steps all have
something to do.

    python scripts/make_samples.py            # writes samples/*.jpg
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "samples"
SS = 3  # supersampling factor for anti-aliased shapes


def font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def scene_background(w: int, h: int, seed: int, horizon: float = 0.62) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    hy = int(h * horizon)
    for y in range(hy):  # sky gradient
        t = y / hy
        d.line([(0, y), (w, y)], fill=(int(120 + 90 * t), int(160 + 70 * t), int(210 + 30 * t)))
    x = 0
    while x < w:  # skyline
        bw = rnd.randint(w // 14, w // 6)
        bh = rnd.randint(h // 8, h // 3)
        shade = rnd.randint(95, 150)
        d.rectangle([x, hy - bh, x + bw, hy], fill=(shade, shade + 5, shade + 15))
        for wy in range(hy - bh + 12, hy - 10, 22):
            for wx in range(x + 8, x + bw - 10, 18):
                if rnd.random() < 0.6:
                    d.rectangle([wx, wy, wx + 8, wy + 10], fill=(225, 215, 160) if rnd.random() < 0.3 else (70, 80, 95))
        x += bw + rnd.randint(2, 12)
    for y in range(hy, h):  # asphalt
        t = (y - hy) / max(1, h - hy)
        v = int(105 - 35 * t)
        d.line([(0, y), (w, y)], fill=(v, v, v + 4))
    noise = Image.effect_noise((w, h), 18).convert("RGB")
    img = Image.blend(img, noise, 0.08)
    d = ImageDraw.Draw(img)
    for i in range(0, w, w // 6):  # lane markings
        d.rectangle([i, int(h * 0.9), i + w // 12, int(h * 0.9) + max(3, h // 120)], fill=(225, 225, 210))
    return img


def plate(text: str, w: int, h: int) -> Image.Image:
    p = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=max(2, h // 8), fill=(246, 246, 240), outline=(20, 20, 20), width=max(2, h // 14))
    f = font(int(h * 0.62))
    bbox = d.textbbox((0, 0), text, font=f)
    d.text(((w - (bbox[2] - bbox[0])) / 2 - bbox[0], (h - (bbox[3] - bbox[1])) / 2 - bbox[1]), text, font=f, fill=(15, 15, 15))
    return p


def watermark(img: Image.Image, text: str) -> Image.Image:
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    f = font(max(18, w // 16))
    d = ImageDraw.Draw(layer)
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tile = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((10, 10 - bbox[1]), text, font=f, fill=(255, 255, 255, 105))
    tile = tile.rotate(18, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(tile, ((w - tile.width) // 2, int(h * 0.30)))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def draw_car(w: int, h: int, body=(196, 32, 40)) -> Image.Image:
    """Side view hatchback on a transparent layer (supersampled)."""
    W, H = w * SS, h * SS
    car = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(car)
    s = lambda x, y: (int(x * W), int(y * H))  # noqa: E731
    d.ellipse([*s(0.12, 0.86), *s(0.88, 0.97)], fill=(0, 0, 0, 90))  # ground shadow
    d.rounded_rectangle([*s(0.10, 0.52), *s(0.90, 0.82)], radius=int(0.06 * H), fill=body)
    d.polygon([s(0.24, 0.53), s(0.34, 0.30), s(0.66, 0.30), s(0.80, 0.53)], fill=body)
    d.polygon([s(0.28, 0.52), s(0.36, 0.34), s(0.49, 0.34), s(0.49, 0.52)], fill=(40, 60, 80))
    d.polygon([s(0.51, 0.52), s(0.51, 0.34), s(0.645, 0.34), s(0.755, 0.52)], fill=(40, 60, 80))
    d.line([s(0.12, 0.64), s(0.88, 0.64)], fill=(150, 20, 28), width=int(0.008 * H))
    d.rectangle([*s(0.86, 0.56), *s(0.90, 0.62)], fill=(255, 210, 90))  # headlight
    d.rectangle([*s(0.10, 0.56), *s(0.125, 0.63)], fill=(200, 20, 20))  # tail light
    for cx in (0.27, 0.73):
        d.ellipse([*s(cx - 0.085, 0.66), *s(cx + 0.085, 0.95)], fill=(22, 22, 24))
        d.ellipse([*s(cx - 0.05, 0.72), *s(cx + 0.05, 0.89)], fill=(175, 178, 185))
        d.ellipse([*s(cx - 0.015, 0.78), *s(cx + 0.015, 0.83)], fill=(90, 90, 95))
    car = car.resize((w, h), Image.LANCZOS)
    pl = plate("VIS 2026", int(w * 0.11), int(h * 0.075))
    car.alpha_composite(pl, (int(w * 0.105), int(h * 0.67)))
    return car


def draw_bike(w: int, h: int) -> Image.Image:
    """Side view motorcycle on a transparent layer (supersampled)."""
    W, H = w * SS, h * SS
    bike = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bike)
    s = lambda x, y: (int(x * W), int(y * H))  # noqa: E731
    lw = int(0.018 * H)
    d.ellipse([*s(0.14, 0.90), *s(0.86, 0.98)], fill=(0, 0, 0, 90))
    for cx in (0.27, 0.74):
        d.ellipse([*s(cx - 0.13, 0.55), *s(cx + 0.13, 0.95)], fill=(20, 20, 22))
        d.ellipse([*s(cx - 0.095, 0.61), *s(cx + 0.095, 0.89)], fill=(60, 62, 66))
        d.ellipse([*s(cx - 0.03, 0.71), *s(cx + 0.03, 0.79)], fill=(190, 190, 195))
    d.line([s(0.27, 0.75), s(0.47, 0.60), s(0.62, 0.62)], fill=(40, 40, 45), width=lw)  # swingarm
    d.line([s(0.74, 0.75), s(0.66, 0.38)], fill=(200, 200, 205), width=lw)  # fork
    d.rounded_rectangle([*s(0.42, 0.55), *s(0.60, 0.74)], radius=int(0.02 * H), fill=(70, 72, 78))  # engine
    d.polygon([s(0.44, 0.50), s(0.50, 0.36), s(0.64, 0.36), s(0.66, 0.50)], fill=(20, 90, 170))  # tank
    d.polygon([s(0.24, 0.47), s(0.44, 0.44), s(0.46, 0.50), s(0.26, 0.52)], fill=(25, 25, 28))  # seat
    d.polygon([s(0.14, 0.50), s(0.26, 0.45), s(0.30, 0.52), s(0.16, 0.55)], fill=(20, 90, 170))  # tail
    d.line([s(0.62, 0.33), s(0.70, 0.30)], fill=(30, 30, 30), width=lw)  # bars
    d.ellipse([*s(0.69, 0.36), *s(0.75, 0.44)], fill=(255, 215, 110))  # headlight
    d.line([s(0.36, 0.78), s(0.20, 0.70)], fill=(185, 185, 190), width=int(0.025 * H))  # exhaust
    bike = bike.resize((w, h), Image.LANCZOS)
    pl = plate("MC 42 X", int(w * 0.10), int(h * 0.07))
    bike.alpha_composite(pl, (int(w * 0.075), int(h * 0.53)))
    return bike


def compose(bg: Image.Image, subject: Image.Image, xy) -> Image.Image:
    out = bg.convert("RGBA")
    out.alpha_composite(subject, xy)
    return out.convert("RGB")


def main() -> None:
    OUT.mkdir(exist_ok=True)

    w, h = 1200, 800
    car = compose(scene_background(w, h, seed=1), draw_car(int(w * 0.86), int(h * 0.62)), (int(w * 0.07), int(h * 0.36)))
    car = watermark(car, "© SAMPLE DEALER")
    car.save(OUT / "hatchback.jpg", quality=90)

    bike = compose(scene_background(w, h, seed=7, horizon=0.58), draw_bike(int(w * 0.82), int(h * 0.66)), (int(w * 0.09), int(h * 0.30)))
    bike = watermark(bike, "© EXAMPLE MOTORS")
    bike.save(OUT / "motorcycle.jpg", quality=90)

    # Low-resolution copy for the upscaling demo (JPEG artefacts included on purpose).
    small = car.resize((320, 213), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.4))
    small.save(OUT / "hatchback-small.jpg", quality=70)

    for p in sorted(OUT.glob("*.jpg")):
        print(p.relative_to(OUT.parent), Image.open(p).size, f"{p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
