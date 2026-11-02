"""Stamp the user's own text watermark onto an image."""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

POSITIONS = ("top-left", "top-center", "top-right", "center", "bottom-left", "bottom-center", "bottom-right")
# Font sizes are given for a 1200 px wide image and scaled with the image width.
REFERENCE_WIDTH = 1200
MIN_FONT_PX = 12
MARGIN_RATIO = 0.03
TILE_ANGLE_DEG = 30
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
)


def parse_hex_color(color: str) -> Tuple[int, int, int]:
    """``#RRGGBB`` -> (r, g, b). Raises ValueError otherwise."""
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError("color must be #RRGGBB")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


@lru_cache(maxsize=32)
def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _anchor(position: str, w: int, h: int, tw: int, th: int) -> Tuple[int, int]:
    margin = int(w * MARGIN_RATIO)
    vertical, _, horizontal = position.partition("-")
    if position == "center":
        return (w - tw) // 2, (h - th) // 2
    x = {"left": margin, "center": (w - tw) // 2, "right": w - tw - margin}[horizontal]
    y = margin if vertical == "top" else h - th - margin
    return x, y


def stamp_text(
    image: Image.Image,
    text: str,
    position: str = "bottom-right",
    opacity: float = 0.5,
    font_size: int = 36,
    color: Tuple[int, int, int] = (255, 255, 255),
    repeat: bool = False,
) -> Image.Image:
    """Return ``image`` (as RGBA) with ``text`` stamped once at ``position``, or tiled diagonally."""
    base = image.convert("RGBA")
    w, h = base.size
    alpha = int(max(0.0, min(1.0, opacity)) * 255)
    px = max(MIN_FONT_PX, int(font_size * (w / REFERENCE_WIDTH)))
    font = _font(px)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top

    if repeat:
        tile = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((10, 10), text, fill=(*color, alpha), font=font)
        tile = tile.rotate(TILE_ANGLE_DEG, expand=True, resample=Image.BICUBIC)
        for y in range(0, h, th + px * 4):
            for x in range(0, w, tw + px * 3):
                overlay.paste(tile, (x, y), tile)
    else:
        x, y = _anchor(position, w, h, tw, th)
        draw.text((x + 2, y + 2), text, fill=(0, 0, 0, max(40, alpha // 2)), font=font)  # drop shadow
        draw.text((x, y), text, fill=(*color, alpha), font=font)

    return Image.alpha_composite(base, overlay)
