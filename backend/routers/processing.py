"""Image-processing endpoints.

Every endpoint accepts either a multipart ``file`` upload or a storage ``key``
(form field, or JSON body for the legacy ``remove-background`` call) and
returns the processed image bytes directly.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from image_edit_providers.base import CLEANUP_PRESETS
from services.background_removal import bg_removal_service
from services.storage import storage
from services.studio_compositor import composite_studio, composite_with_template, smart_mirror
from services.upscale_service import SUPPORTED_SCALES, upscale_service
from utils.image_helpers import bytes_to_pil, pil_to_bytes

router = APIRouter(prefix="/api/process", tags=["processing"])

MAX_INPUT_BYTES = 25 * 1024 * 1024


class ProcessRequest(BaseModel):
    key: str


def _png(img: Image.Image) -> Response:
    return Response(content=pil_to_bytes(img, fmt="PNG"), media_type="image/png")


async def _read_input(file: Optional[UploadFile], key: Optional[str]) -> bytes:
    if file is not None:
        data = await file.read()
    elif key:
        try:
            data = storage.download_image(key)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Image not found: {e}")
    else:
        raise HTTPException(status_code=400, detail="Provide a 'file' upload or a storage 'key'")
    if len(data) > MAX_INPUT_BYTES:
        raise HTTPException(status_code=400, detail="Image too large. Max 25 MB.")
    return data


@router.post("/remove-background")
async def remove_background(request: Request):
    """Remove the background. Multipart ``file`` or JSON ``{"key": ...}``. Returns RGBA PNG."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded = form.get("file")
        key = form.get("key")
        data = await _read_input(uploaded if uploaded is not None and not isinstance(uploaded, str) else None,
                                 key if isinstance(key, str) else None)
    else:
        body = await request.json()
        data = await _read_input(None, body.get("key"))
    try:
        result = bg_removal_service.remove_background(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return Response(content=result, media_type="image/png")


@router.post("/upscale")
async def upscale(
    file: Optional[UploadFile] = File(None),
    key: Optional[str] = Form(None),
    scale: int = Form(4),
):
    """Real-ESRGAN super-resolution at 2x, 4x or 8x. Alpha is preserved."""
    if scale not in SUPPORTED_SCALES:
        raise HTTPException(400, f"scale must be one of {SUPPORTED_SCALES}")
    data = await _read_input(file, key)
    try:
        result = upscale_service.upscale(bytes_to_pil(data), scale=scale)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _png(result)


@router.post("/enhance")
async def enhance(file: Optional[UploadFile] = File(None), key: Optional[str] = Form(None)):
    """Detail enhancement at the original size (4x Real-ESRGAN, then Lanczos back down)."""
    data = await _read_input(file, key)
    try:
        image = bytes_to_pil(data)
        w, h = image.size
        result = upscale_service.upscale(image, scale=4).resize((w, h), Image.LANCZOS)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _png(result)


@router.post("/studio-composite")
async def studio_composite(request: ProcessRequest):
    """Remove the background and place the vehicle on a white studio backdrop."""
    data = await _read_input(None, request.key)
    try:
        subject = bytes_to_pil(bg_removal_service.remove_background(data))
        return _png(composite_studio(subject))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/composite-template")
async def composite_template(
    key: str = Form(...),
    template: Optional[str] = Form(None),
    template_file: Optional[UploadFile] = File(None),
):
    """Cut out the vehicle and composite it over the white studio or an uploaded backdrop."""
    data = await _read_input(None, key)
    try:
        subject = bytes_to_pil(bg_removal_service.remove_background(data))
        if template_file is not None:
            bg_image = bytes_to_pil(await template_file.read())
            return _png(composite_with_template(subject, bg_image))
        return _png(composite_studio(subject))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mirror")
async def mirror(file: Optional[UploadFile] = File(None), key: Optional[str] = Form(None)):
    """Flip horizontally (keeps detected text readable when EasyOCR is installed)."""
    data = await _read_input(file, key)
    return _png(smart_mirror(bytes_to_pil(data)))


@router.post("/crop")
async def crop(
    file: Optional[UploadFile] = File(None),
    key: Optional[str] = Form(None),
    crop_x: int = Form(...),
    crop_y: int = Form(...),
    crop_w: int = Form(...),
    crop_h: int = Form(...),
):
    data = await _read_input(file, key)
    image = bytes_to_pil(data)
    w, h = image.size
    x1, y1 = max(0, crop_x), max(0, crop_y)
    x2, y2 = min(w, crop_x + crop_w), min(h, crop_y + crop_h)
    if x2 <= x1 or y2 <= y1:
        raise HTTPException(status_code=400, detail="Invalid crop region")
    return _png(image.crop((x1, y1, x2, y2)))


@router.post("/watermark")
async def watermark(
    file: Optional[UploadFile] = File(None),
    key: Optional[str] = Form(None),
    text: str = Form(...),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.5),
    font_size: int = Form(36),
    color: str = Form("#FFFFFF"),
    repeat: bool = Form(False),
):
    """Stamp your own text watermark onto a cleaned image."""
    data = await _read_input(file, key)
    image = bytes_to_pil(data).convert("RGBA")
    w, h = image.size
    hex_color = color.lstrip("#")
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    except ValueError:
        raise HTTPException(400, "color must be #RRGGBB")
    alpha = int(max(0.0, min(1.0, opacity)) * 255)
    scaled_size = max(12, int(font_size * (w / 1200)))

    font = None
    for font_path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, scaled_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    if repeat:
        step_x, step_y = tw + scaled_size * 3, th + scaled_size * 4
        for yi in range(0, h, step_y):
            for xi in range(0, w, step_x):
                tile = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
                ImageDraw.Draw(tile).text((10, 10), text, fill=(r, g, b, alpha), font=font)
                rotated = tile.rotate(30, expand=True, resample=Image.BICUBIC)
                overlay.paste(rotated, (xi, yi), rotated)
    else:
        margin = int(w * 0.03)
        positions = {
            "top-left": (margin, margin),
            "top-right": (w - tw - margin, margin),
            "top-center": ((w - tw) // 2, margin),
            "center": ((w - tw) // 2, (h - th) // 2),
            "bottom-left": (margin, h - th - margin),
            "bottom-right": (w - tw - margin, h - th - margin),
            "bottom-center": ((w - tw) // 2, h - th - margin),
        }
        x, y = positions.get(position, positions["bottom-right"])
        draw.text((x + 2, y + 2), text, fill=(0, 0, 0, max(40, alpha // 2)), font=font)
        draw.text((x, y), text, fill=(r, g, b, alpha), font=font)

    return _png(Image.alpha_composite(image, overlay))


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "bg_model": bg_removal_service.model_name,
        "bg_model_loaded": bg_removal_service.is_loaded,
        "upscaler_loaded": upscale_service.is_loaded,
    }


# --- AI inpainting (optional, needs an API key) -------------------------------


@router.get("/llm-edit/presets")
async def llm_edit_presets():
    """Built-in clean-up prompts (number plate removal, watermark removal, ...)."""
    return [{"id": k, "label": v["label"], "prompt": v["prompt"]} for k, v in CLEANUP_PRESETS.items()]


@router.post("/llm-edit")
async def llm_edit_image(
    file: Optional[UploadFile] = File(None),
    key: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    preset: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    quality: str = Form("medium"),
):
    """Edit an image with Gemini or OpenAI using a preset (``remove_plate``,
    ``remove_watermark``, ...) or a free-form ``prompt``."""
    from image_edit_providers import create_image_edit_provider
    from image_edit_providers.base import ImageEditError

    if preset:
        if preset not in CLEANUP_PRESETS:
            raise HTTPException(400, f"Unknown preset. Choose from: {', '.join(CLEANUP_PRESETS)}")
        prompt = CLEANUP_PRESETS[preset]["prompt"]
    if not prompt:
        raise HTTPException(400, "Provide 'prompt' or 'preset'")

    editor = create_image_edit_provider(provider)
    if not editor:
        raise HTTPException(
            503,
            "No image edit provider configured. Set OPENAI_API_KEY or GEMINI_API_KEY in .env",
        )

    image_bytes = await _read_input(file, key)
    try:
        result = await editor.edit_image(image_bytes=image_bytes, prompt=prompt, quality=quality)
    except ImageEditError as e:
        raise HTTPException(429 if e.retryable else 502, str(e))

    return Response(
        content=result.image_bytes,
        media_type="image/png",
        headers={
            "X-Edit-Provider": result.provider,
            "X-Edit-Model": result.model,
            "X-Edit-Cost-USD": str(result.cost_estimate_usd or ""),
        },
    )


@router.get("/llm-edit/providers")
async def list_edit_providers():
    """Which image-edit providers have an API key configured."""
    from image_edit_providers import create_image_edit_provider

    providers = []
    for name in ("openai", "gemini"):
        editor = create_image_edit_provider(name)
        if editor:
            providers.append({
                "name": name,
                "available": await editor.check_available(),
                "models": [editor.model],
            })
    return {"providers": providers}
