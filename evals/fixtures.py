"""Synthetic eval fixtures with exact ground truth, generated in code.

Every scene reuses the drawing functions of ``scripts/make_samples.py`` (the
same procedural car and motorcycle as the bundled samples), so nothing is
downloaded and every mask is known exactly:

* ``subject_mask``: the vehicle layer's alpha > 127, placed at its known offset.
  The soft ground shadow is drawn at alpha 90, so it is background in the ground
  truth (a cut-out should not keep it).
* ``plate_mask``: the number plate's rectangle, from the offsets in make_samples.
* ``watermark_mask``: bounding box of the pixels the semi-transparent watermark changed.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENE_SIZE = (960, 640)
BODY_COLOURS = [(196, 32, 40), (30, 70, 160), (235, 235, 235), (25, 25, 28), (210, 150, 30), (60, 120, 70)]
WATERMARKS = ["© SAMPLE DEALER", "© EXAMPLE MOTORS"]
# Plate placement inside the vehicle layer, as fractions of the layer size:
# (x, y, w, h). Mirrors draw_car / draw_bike in scripts/make_samples.py; a sanity
# check in build_scene() fails loudly if the two drift apart.
PLATE_BOX = {"car": (0.105, 0.67, 0.11, 0.075), "bike": (0.075, 0.53, 0.10, 0.07)}
PLATE_FILL = (246, 246, 240)


@lru_cache(maxsize=1)
def samples_module():
    path = REPO_ROOT / "scripts" / "make_samples.py"
    spec = importlib.util.spec_from_file_location("make_samples", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Scene:
    name: str
    kind: str  # "car" | "bike"
    image: Image.Image  # RGB, with plate and watermark
    subject_mask: np.ndarray  # bool HxW
    plate_mask: np.ndarray
    watermark_mask: np.ndarray

    @property
    def edit_mask(self) -> np.ndarray:
        """Region a plate + watermark clean-up is allowed to change."""
        return self.plate_mask | self.watermark_mask


def _box_mask(shape, x: int, y: int, w: int, h: int) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    m[max(0, y):y + h, max(0, x):x + w] = True
    return m


def build_scene(index: int, size=SCENE_SIZE) -> Scene:
    """Scene ``index`` (deterministic): alternating car/bike, varied background, colour, scale and position."""
    ms = samples_module()
    w, h = size
    kind = "car" if index % 2 == 0 else "bike"
    horizon = 0.55 + 0.02 * (index % 6)
    background = ms.scene_background(w, h, seed=100 + index, horizon=horizon)

    sw = int(w * (0.70 + 0.03 * (index % 6)))  # subject 70-85% of the width
    sh = int(h * (0.56 + 0.02 * (index % 5)))
    if kind == "car":
        subject = ms.draw_car(sw, sh, body=BODY_COLOURS[index % len(BODY_COLOURS)])
    else:
        subject = ms.draw_bike(sw, sh)
    x = int((w - sw) * (0.2 + 0.15 * (index % 5)))
    y = h - sh - int(h * 0.02 * (index % 3))

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(subject, (x, y))
    subject_mask = np.asarray(canvas.getchannel("A")) > 127
    composed = ms.compose(background, subject, (x, y))

    fx, fy, fw, fh = PLATE_BOX[kind]
    px, py, pw, ph = x + int(sw * fx), y + int(sh * fy), int(sw * fw), int(sh * fh)
    plate_mask = _box_mask(subject_mask.shape, px, py, pw, ph)
    # Sanity check: most of the box is plate colour (catches drift from make_samples.py).
    box = np.asarray(composed)[py:py + ph, px:px + pw].astype(int)
    if (np.abs(box - PLATE_FILL).max(axis=-1) < 12).mean() < 0.5:
        raise RuntimeError(f"plate box for '{kind}' no longer matches scripts/make_samples.py")

    marked = ms.watermark(composed, WATERMARKS[index % len(WATERMARKS)])
    changed = np.abs(np.asarray(marked, dtype=np.int16) - np.asarray(composed, dtype=np.int16)).max(axis=-1) > 0
    ys, xs = np.nonzero(changed)
    watermark_mask = _box_mask(changed.shape, int(xs.min()), int(ys.min()),
                               int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))

    return Scene(f"{kind}-{index:02d}", kind, marked, subject_mask, plate_mask, watermark_mask)


def build_scenes(count: int = 20, size=SCENE_SIZE) -> list:
    return [build_scene(i, size) for i in range(count)]


def jpeg_roundtrip(image: Image.Image, quality: int = 92) -> Image.Image:
    import io

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


# --- Gemini responses ---------------------------------------------------------
# API-shaped generateContent JSON with a synthetic image, parsed by the real SDK
# (types.GenerateContentResponse.model_validate). They exercise the adapter's
# response handling, not the model: no request is ever sent.


def gemini_image_response(png_bytes: bytes) -> dict:
    import base64

    return {
        "candidates": [{
            "content": {"role": "model", "parts": [
                {"text": "Here is the edited image."},
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png_bytes).decode()}},
            ]},
            "finishReason": "STOP",
        }],
        "modelVersion": "gemini-2.5-flash-image",
    }


def gemini_blocked_response() -> dict:
    """What a safety-blocked edit looks like: a candidate with a finish reason and no content."""
    return {"candidates": [{"finishReason": "PROHIBITED_CONTENT"}], "modelVersion": "gemini-2.5-flash-image"}
