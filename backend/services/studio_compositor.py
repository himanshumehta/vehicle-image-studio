from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter
from typing import List
import numpy as np
import logging

try:
    import easyocr
    _ocr_reader = None
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

logger = logging.getLogger(__name__)


def _get_ocr_reader():
    """Lazy-load EasyOCR reader (downloads model on first call)."""
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
        logger.info("EasyOCR reader initialized")
    return _ocr_reader


FLOOR_RATIO = 0.65
PADDING_RATIO = 0.1


def _create_gradient_background(width: int, height: int) -> Image.Image:
    """White studio gradient: pure white top -> light gray at floor -> slightly darker below."""
    arr = np.full((height, width, 3), 255, dtype=np.uint8)
    for y in range(height):
        ratio = y / height
        if ratio < 0.65:
            t = ratio / 0.65
            v = int(255 - t * 15)  # 255 -> 240
            arr[y, :] = [v, v, v]
        else:
            t = (ratio - 0.65) / 0.35
            v = int(240 - t * 20)  # 240 -> 220
            arr[y, :] = [v, v, v]
    return Image.fromarray(arr, "RGB")


def _apply_vignette(bg: Image.Image) -> Image.Image:
    """Subtle edge darkening for white background."""
    width, height = bg.size
    Y, X = np.ogrid[:height, :width]
    cx, cy = width / 2, height / 2
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    # Light vignette: edges go from 1.0 down to ~0.92
    vignette = np.clip(1 - (dist / max_dist) * 0.08, 0.92, 1.0).astype(np.float32)

    bg_arr = np.array(bg, dtype=np.float32)
    result = (bg_arr * vignette[:, :, np.newaxis]).astype(np.uint8)
    return Image.fromarray(result, "RGB")


def _draw_floor_line(bg: Image.Image, floor_y: int) -> Image.Image:
    """Subtle floor horizon line for white studio."""
    draw = ImageDraw.Draw(bg)
    width = bg.size[0]
    for i in range(-1, 2):
        v = 210 if i == 0 else 225
        draw.line([(0, floor_y + i), (width, floor_y + i)], fill=(v, v, v))
    return bg


def _create_contact_shadow(subject: Image.Image, canvas_size: tuple, x_offset: int, floor_y: int) -> Image.Image:
    """Contact shadow from subject alpha."""
    alpha = subject.split()[3]
    shadow_width = alpha.size[0]
    shadow_height = max(1, int(alpha.size[1] * 0.08))
    shadow = alpha.resize((shadow_width, shadow_height), Image.LANCZOS)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(5, shadow_height // 2)))

    shadow_data = shadow.point(lambda p: min(p, 80))  # lighter shadow for white bg
    shadow_rgba = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    shadow_rgba.putalpha(shadow_data)

    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    paste_y = floor_y - shadow_height // 2
    layer.paste(shadow_rgba, (x_offset, paste_y), shadow_rgba)
    return layer


def _create_reflection(subject: Image.Image) -> Image.Image:
    """Vertically flipped subject with gradient fade-out, darkened and blurred."""
    reflection = subject.transpose(Image.FLIP_TOP_BOTTOM)
    width, height = reflection.size

    fade_height = int(height * 0.25)
    grad = np.zeros(height, dtype=np.float32)
    if fade_height > 0:
        grad[:fade_height] = np.linspace(40, 0, fade_height) / 255.0  # softer for white bg

    orig_a = np.array(reflection.split()[3], dtype=np.float32) / 255.0
    new_a = np.minimum(grad[:, np.newaxis] * np.ones(width), orig_a)

    arr = np.array(reflection, dtype=np.float32)
    arr[:, :, :3] *= 0.5
    arr[:, :, 3] = new_a * 255
    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return result.filter(ImageFilter.GaussianBlur(radius=3))


def composite_with_template(subject_rgba: Image.Image, template: Image.Image) -> Image.Image:
    """Composite a transparent subject over a template background.

    Resizes template to cover subject dimensions (cover-fit, center-crop),
    then composites the subject on top.
    """
    if subject_rgba.mode != "RGBA":
        subject_rgba = subject_rgba.convert("RGBA")

    sw, sh = subject_rgba.size
    tw, th = template.size

    # Cover-fit: scale template so it fully covers subject dimensions, then center-crop
    scale = max(sw / tw, sh / th)
    new_tw = int(tw * scale)
    new_th = int(th * scale)
    template_resized = template.resize((new_tw, new_th), Image.LANCZOS)

    # Center-crop to subject size
    left = (new_tw - sw) // 2
    top = (new_th - sh) // 2
    template_cropped = template_resized.crop((left, top, left + sw, top + sh))

    # Composite subject over template
    canvas = template_cropped.convert("RGBA")
    canvas = Image.alpha_composite(canvas, subject_rgba)
    return canvas.convert("RGB")


def composite_studio(subject_rgba: Image.Image) -> Image.Image:
    """White studio background with auto-centered subject."""
    if subject_rgba.mode != "RGBA":
        subject_rgba = subject_rgba.convert("RGBA")

    w, h = subject_rgba.size

    # Find bounding box of non-transparent pixels and center the subject
    bbox = subject_rgba.getbbox()  # (left, top, right, bottom) of non-transparent area
    if bbox:
        cropped = subject_rgba.crop(bbox)
        cw, ch = cropped.size

        # Create a new RGBA canvas at original dimensions
        centered = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        # Center horizontally, place on lower portion vertically (floor at 65%)
        paste_x = (w - cw) // 2
        # Vertically: bottom of subject sits at ~85% of canvas height
        target_bottom = int(h * 0.85)
        paste_y = max(0, target_bottom - ch)

        centered.paste(cropped, (paste_x, paste_y))
        subject_rgba = centered

    # White background, same size as subject
    bg = _create_gradient_background(w, h)
    bg = _apply_vignette(bg)

    canvas = bg.convert("RGBA")
    canvas = Image.alpha_composite(canvas, subject_rgba)

    return canvas.convert("RGB")


def _create_feather_mask(width: int, height: int, feather: int = 12) -> Image.Image:
    """Create a soft-edge mask: white center fading to black at edges."""
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    if width > feather * 2 and height > feather * 2:
        draw.rectangle(
            [(feather, feather), (width - feather - 1, height - feather - 1)],
            fill=255,
        )
    else:
        draw.rectangle([(0, 0), (width - 1, height - 1)], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(radius=feather))


def _merge_text_boxes(boxes: List[dict], gap: int = 30) -> List[dict]:
    """Merge nearby text bounding boxes into larger regions."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b["x"])
    merged = [boxes[0].copy()]
    for b in boxes[1:]:
        prev = merged[-1]
        # Check horizontal overlap/proximity and vertical alignment
        h_close = b["x"] <= prev["x"] + prev["w"] + gap
        v_overlap = not (b["y"] > prev["y"] + prev["h"] + gap or
                         b["y"] + b["h"] < prev["y"] - gap)
        if h_close and v_overlap:
            nx = min(prev["x"], b["x"])
            ny = min(prev["y"], b["y"])
            nx2 = max(prev["x"] + prev["w"], b["x"] + b["w"])
            ny2 = max(prev["y"] + prev["h"], b["y"] + b["h"])
            prev["x"], prev["y"] = nx, ny
            prev["w"], prev["h"] = nx2 - nx, ny2 - ny
        else:
            merged.append(b.copy())
    return merged


def smart_mirror(image: Image.Image) -> Image.Image:
    """Mirror image horizontally while preserving readable text.

    Uses EasyOCR (scene text detection) to find brand names / text on the
    bike, mirrors the full image, then un-mirrors detected text regions
    so they stay readable. Falls back to simple mirror if EasyOCR is
    unavailable or detection fails.
    """
    if not HAS_EASYOCR:
        logger.info("EasyOCR not available, using simple mirror")
        return image.transpose(Image.FLIP_LEFT_RIGHT)

    was_rgba = image.mode == "RGBA"
    if was_rgba:
        alpha_channel = image.split()[3]
        rgb_image = image.convert("RGB")
    else:
        rgb_image = image if image.mode == "RGB" else image.convert("RGB")

    w, h = rgb_image.size
    img_array = np.array(rgb_image)

    # Detect text with EasyOCR (scene text — works on stylized brand text)
    try:
        reader = _get_ocr_reader()
        results = reader.readtext(img_array)
    except Exception as e:
        logger.warning("EasyOCR failed, using simple mirror: %s", e)
        return image.transpose(Image.FLIP_LEFT_RIGHT)

    # Convert EasyOCR polygon results to axis-aligned bounding boxes
    boxes = []
    for bbox, text, conf in results:
        text = text.strip()
        if conf > 0.2 and len(text) >= 1:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            boxes.append({
                "x": int(min(xs)),
                "y": int(min(ys)),
                "w": int(max(xs) - min(xs)),
                "h": int(max(ys) - min(ys)),
                "text": text,
                "conf": conf,
            })

    if not boxes:
        logger.info("No text detected, using simple mirror")
        return image.transpose(Image.FLIP_LEFT_RIGHT)

    # Merge nearby boxes (brand names are often multi-word)
    merged = _merge_text_boxes(boxes)
    detected_texts = [b.get("text", "") for b in boxes]
    logger.info("Detected %d text regions (%d merged): %s",
                len(boxes), len(merged), detected_texts)

    # Mirror the full image
    mirrored = rgb_image.transpose(Image.FLIP_LEFT_RIGHT)

    # For each text region: un-mirror it and blend back
    for box in merged:
        pad = max(10, int(min(box["w"], box["h"]) * 0.25))
        x1 = max(0, box["x"] - pad)
        y1 = max(0, box["y"] - pad)
        x2 = min(w, box["x"] + box["w"] + pad)
        y2 = min(h, box["y"] + box["h"] + pad)

        region_w = x2 - x1
        region_h = y2 - y1
        if region_w < 4 or region_h < 4:
            continue

        # Mirrored position of this region
        mx1 = w - x2
        mx2 = w - x1

        # Crop from mirrored image and un-mirror (restores readable text)
        region = mirrored.crop((mx1, y1, mx2, y2))
        region_fixed = region.transpose(Image.FLIP_LEFT_RIGHT)

        # Feathered blend for smooth edges
        feather = min(pad, max(8, int(min(region_w, region_h) * 0.15)))
        mask = _create_feather_mask(region_w, region_h, feather=feather)
        mirrored.paste(region_fixed, (mx1, y1), mask)

    if was_rgba:
        alpha_mirrored = alpha_channel.transpose(Image.FLIP_LEFT_RIGHT)
        mirrored = mirrored.convert("RGBA")
        mirrored.putalpha(alpha_mirrored)

    return mirrored
