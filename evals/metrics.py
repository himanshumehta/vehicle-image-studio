"""Image metrics for the offline evals. Pure NumPy/OpenCV, no app imports.

``edit_preservation`` answers "did the edit stay inside its mask?" for any
inpainting result (plate or watermark removal): pixels outside the mask must be
unchanged up to a tolerance. ``mask_iou`` scores a predicted cut-out against a
known ground-truth mask.

Images are compared on their RGB channels only (alpha is ignored), as uint8.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

# A pixel counts as changed when any RGB channel moved by more than this (0-255).
DEFAULT_CHANGE_THRESHOLD = 8
# The edit mask is grown by this many pixels before measuring, so blending at the
# mask boundary is not counted as bleed.
DEFAULT_MARGIN_PX = 3
# Width of the ring just outside the (grown) mask where bleeding edits show up first.
DEFAULT_BAND_PX = 32
# PSNR of identical regions is infinite; it is reported as this cap instead.
PSNR_CAP_DB = 99.0


def to_rgb_array(image) -> np.ndarray:
    """PIL image or array -> HxWx3 uint8 array."""
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGB"), dtype=np.uint8)
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    return arr[..., :3].astype(np.uint8)


def to_bool_mask(mask, threshold: int = 127) -> np.ndarray:
    """PIL "L" image, uint8 array or bool array -> HxW bool array (True = inside)."""
    if isinstance(mask, Image.Image):
        mask = np.asarray(mask.convert("L"))
    arr = np.asarray(mask)
    if arr.dtype == bool:
        return arr
    if arr.dtype.kind == "f":
        return arr > 0.5
    return arr > threshold


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(mask.astype(np.uint8), kernel) > 0


def psnr(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """PSNR in dB over two equally shaped uint8 pixel sets; None if empty, capped when identical."""
    if a.size == 0:
        return None
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    if mse == 0:
        return PSNR_CAP_DB
    return min(PSNR_CAP_DB, 10 * math.log10(255.0 ** 2 / mse))


@dataclass
class PreservationScore:
    size_match: bool
    changed_outside_frac: Optional[float]  # share of outside-mask pixels that changed
    psnr_outside_db: Optional[float]
    max_abs_diff_outside: Optional[int]
    changed_near_mask_frac: Optional[float]  # same, in a ring just outside the mask (bleed shows here)
    changed_inside_frac: Optional[float]  # share of in-mask pixels that changed (did the edit happen?)
    outside_pixels: int
    inside_pixels: int
    threshold: int
    margin_px: int
    band_px: int

    def to_dict(self) -> dict:
        return asdict(self)


def edit_preservation(
    before,
    after,
    mask,
    *,
    threshold: int = DEFAULT_CHANGE_THRESHOLD,
    margin_px: int = DEFAULT_MARGIN_PX,
    band_px: int = DEFAULT_BAND_PX,
) -> PreservationScore:
    """Measure how much an edit changed the image outside ``mask``.

    ``mask`` marks the region the edit was allowed to touch (plate, watermark).
    If ``after`` has a different size the comparison is undefined: the score has
    ``size_match=False`` and no pixel metrics (resampling would hide the change).
    """
    b = to_rgb_array(before)
    a = to_rgb_array(after)
    m = to_bool_mask(mask)
    if m.shape != b.shape[:2]:
        raise ValueError(f"mask is {m.shape[::-1]}, image is {b.shape[1::-1]}")
    allowed = dilate(m, margin_px)
    outside = ~allowed
    near = dilate(allowed, band_px) & outside
    if a.shape != b.shape:
        return PreservationScore(
            False, None, None, None, None, None, int(outside.sum()), int(m.sum()), threshold, margin_px, band_px
        )

    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=-1)
    changed = diff > threshold
    n_out, n_in = int(outside.sum()), int(m.sum())
    return PreservationScore(
        size_match=True,
        changed_outside_frac=float(changed[outside].mean()) if n_out else None,
        psnr_outside_db=psnr(a[outside], b[outside]),
        max_abs_diff_outside=int(diff[outside].max()) if n_out else None,
        changed_near_mask_frac=float(changed[near].mean()) if near.any() else None,
        changed_inside_frac=float(changed[m].mean()) if n_in else None,
        outside_pixels=n_out,
        inside_pixels=n_in,
        threshold=threshold,
        margin_px=margin_px,
        band_px=band_px,
    )


# Verdict gates for an edit. These are design choices, stated here once.
MAX_CHANGED_OUTSIDE = 0.01  # at most 1% of outside pixels may move by more than the threshold
MIN_PSNR_OUTSIDE_DB = 35.0
MIN_CHANGED_INSIDE = 0.05  # the edit must visibly change at least 5% of the masked pixels


def preservation_verdict(score: PreservationScore) -> str:
    """"pass", or the first reason the edit fails."""
    if not score.size_match:
        return "size_mismatch"
    if score.changed_outside_frac is not None and score.changed_outside_frac > MAX_CHANGED_OUTSIDE:
        return "changed_outside_mask"
    if score.psnr_outside_db is not None and score.psnr_outside_db < MIN_PSNR_OUTSIDE_DB:
        return "low_psnr_outside_mask"
    if score.changed_inside_frac is not None and score.changed_inside_frac < MIN_CHANGED_INSIDE:
        return "no_edit_inside_mask"
    return "pass"


def mask_iou(pred, gt) -> float:
    """Intersection over union of two masks (binarised at 50%). Two empty masks score 1.0."""
    p, g = to_bool_mask(pred), to_bool_mask(gt)
    if p.shape != g.shape:
        raise ValueError(f"mask shapes differ: {p.shape} vs {g.shape}")
    union = int(np.logical_or(p, g).sum())
    if union == 0:
        return 1.0
    return float(np.logical_and(p, g).sum()) / union
