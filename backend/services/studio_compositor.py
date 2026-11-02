"""Place a cut-out vehicle on a white studio backdrop or on a user-supplied background."""
from __future__ import annotations

import numpy as np
from PIL import Image

# White studio backdrop: brightness falls from TOP_LEVEL to HORIZON_LEVEL down to
# the floor line, then to FLOOR_LEVEL at the bottom edge.
HORIZON_RATIO = 0.65
TOP_LEVEL, HORIZON_LEVEL, FLOOR_LEVEL = 255, 240, 220
# Corners are darkened by at most this fraction.
VIGNETTE_STRENGTH = 0.08
# The bottom of the vehicle sits at this fraction of the canvas height.
SUBJECT_BOTTOM_RATIO = 0.85


def _create_gradient_background(width: int, height: int) -> Image.Image:
    """Vertical white-to-light-grey studio gradient."""
    ratio = np.arange(height, dtype=np.float64) / height
    above = TOP_LEVEL - (ratio / HORIZON_RATIO) * (TOP_LEVEL - HORIZON_LEVEL)
    below = HORIZON_LEVEL - ((ratio - HORIZON_RATIO) / (1 - HORIZON_RATIO)) * (HORIZON_LEVEL - FLOOR_LEVEL)
    rows = np.trunc(np.where(ratio < HORIZON_RATIO, above, below)).astype(np.uint8)
    arr = np.broadcast_to(rows[:, None, None], (height, width, 3))
    return Image.fromarray(np.ascontiguousarray(arr), "RGB")


def _apply_vignette(bg: Image.Image) -> Image.Image:
    """Subtle radial darkening towards the corners."""
    width, height = bg.size
    y, x = np.ogrid[:height, :width]
    cx, cy = width / 2, height / 2
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx**2 + cy**2)
    vignette = np.clip(1 - dist * VIGNETTE_STRENGTH, 1 - VIGNETTE_STRENGTH, 1.0).astype(np.float32)
    result = (np.asarray(bg, dtype=np.float32) * vignette[:, :, None]).astype(np.uint8)
    return Image.fromarray(result, "RGB")


def composite_with_template(subject_rgba: Image.Image, template: Image.Image) -> Image.Image:
    """Composite a transparent subject over ``template``, cover-fitted and centre-cropped."""
    subject_rgba = subject_rgba.convert("RGBA")
    sw, sh = subject_rgba.size
    tw, th = template.size

    scale = max(sw / tw, sh / th)
    new_tw, new_th = max(sw, int(tw * scale)), max(sh, int(th * scale))
    resized = template.resize((new_tw, new_th), Image.LANCZOS)
    left, top = (new_tw - sw) // 2, (new_th - sh) // 2
    canvas = resized.crop((left, top, left + sw, top + sh)).convert("RGBA")
    return Image.alpha_composite(canvas, subject_rgba).convert("RGB")


def composite_studio(subject_rgba: Image.Image) -> Image.Image:
    """White studio backdrop with the subject centred horizontally and grounded near the bottom."""
    subject_rgba = subject_rgba.convert("RGBA")
    w, h = subject_rgba.size

    bbox = subject_rgba.getbbox()  # extent of non-transparent pixels
    if bbox:
        cropped = subject_rgba.crop(bbox)
        cw, ch = cropped.size
        centred = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        centred.paste(cropped, ((w - cw) // 2, max(0, int(h * SUBJECT_BOTTOM_RATIO) - ch)))
        subject_rgba = centred

    canvas = _apply_vignette(_create_gradient_background(w, h)).convert("RGBA")
    return Image.alpha_composite(canvas, subject_rgba).convert("RGB")
