"""Image-processing endpoints.

Every endpoint takes multipart form data with either a ``file`` upload or a
storage ``key`` and returns the processed image as PNG bytes. CPU work runs in
a worker thread under the job limiter (``services/jobs.py``), so a long upscale
never blocks the event loop.
"""
from __future__ import annotations

import logging
from typing import Callable, Literal, Optional, Union

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image

from image_edit_providers import PROVIDERS, create_image_edit_provider
from image_edit_providers.base import CLEANUP_PRESETS, ImageEditError
from routers.uploads import read_upload
from services.background_removal import bg_removal_service
from services.errors import ImageTooLargeError, ModelUnavailableError
from services.jobs import ServerBusyError, get_job_limiter
from services.storage import InvalidKeyError, storage
from services.studio_compositor import composite_studio, composite_with_template
from services.upscale_service import SUPPORTED_SCALES, check_upscale_size, upscale_service
from services.watermark import POSITIONS, parse_hex_color, stamp_text
from utils.image_helpers import ImageValidationError, decode_image, pil_to_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/process", tags=["processing"])

MAX_PROMPT_CHARS = 2000
MAX_WATERMARK_CHARS = 200


async def _read_input(file: Optional[UploadFile], key: Optional[str]) -> bytes:
    """Bytes of the uploaded ``file``, or of the stored image at ``key``."""
    if file is not None:
        return await read_upload(file)
    if not key:
        raise HTTPException(400, "Provide a 'file' upload or a storage 'key'")
    try:
        return storage.download_image(key)
    except InvalidKeyError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(404, "Image not found")


async def _run_job(fn: Callable[[], Union[Image.Image, bytes]]) -> Response:
    """Run ``fn`` under the job limiter and return its image as PNG, mapping failures to status codes."""
    try:
        result = await get_job_limiter().run(fn)
    except ServerBusyError as e:
        raise HTTPException(
            503, "Another image job is running; retry shortly", headers={"Retry-After": str(e.retry_after_s)}
        )
    except ImageValidationError as e:
        raise HTTPException(400, str(e))
    except ImageTooLargeError as e:
        raise HTTPException(413, str(e))
    except ModelUnavailableError as e:
        logger.error("Model unavailable: %s", e)
        raise HTTPException(503, str(e))
    except Exception:
        logger.exception("Image job failed")
        raise HTTPException(500, "Processing failed; see the server log")
    content = result if isinstance(result, bytes) else pil_to_bytes(result, fmt="PNG")
    return Response(content=content, media_type="image/png")


@router.post("/remove-background")
async def remove_background(file: Optional[UploadFile] = File(None), key: Optional[str] = Form(None)):
    """Cut out the vehicle. Returns an RGBA PNG."""
    data = await _read_input(file, key)
    return await _run_job(lambda: bg_removal_service.remove_background(data))


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

    def job() -> Image.Image:
        image = decode_image(data)
        check_upscale_size(image.width, image.height, scale)
        return upscale_service.upscale(image, scale=scale)

    return await _run_job(job)


@router.post("/enhance")
async def enhance(file: Optional[UploadFile] = File(None), key: Optional[str] = Form(None)):
    """Detail enhancement at the original size (4x Real-ESRGAN, then Lanczos back down)."""
    data = await _read_input(file, key)

    def job() -> Image.Image:
        image = decode_image(data)
        check_upscale_size(image.width, image.height, 4)
        return upscale_service.upscale(image, scale=4).resize(image.size, Image.LANCZOS)

    return await _run_job(job)


@router.post("/composite-template")
async def composite_template(key: str = Form(...), template_file: Optional[UploadFile] = File(None)):
    """Cut out the vehicle and composite it over the white studio or an uploaded backdrop."""
    data = await _read_input(None, key)
    background = await read_upload(template_file) if template_file is not None else None

    def job() -> Image.Image:
        subject = decode_image(bg_removal_service.remove_background(data))
        if background is None:
            return composite_studio(subject)
        return composite_with_template(subject, decode_image(background))

    return await _run_job(job)


@router.post("/mirror")
async def mirror(file: Optional[UploadFile] = File(None), key: Optional[str] = Form(None)):
    """Flip horizontally."""
    data = await _read_input(file, key)
    return await _run_job(lambda: decode_image(data).transpose(Image.FLIP_LEFT_RIGHT))


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

    def job() -> Image.Image:
        image = decode_image(data)
        w, h = image.size
        x1, y1 = max(0, crop_x), max(0, crop_y)
        x2, y2 = min(w, crop_x + crop_w), min(h, crop_y + crop_h)
        if x2 <= x1 or y2 <= y1:
            raise ImageValidationError("Invalid crop region")
        return image.crop((x1, y1, x2, y2))

    return await _run_job(job)


@router.post("/watermark")
async def watermark(
    file: Optional[UploadFile] = File(None),
    key: Optional[str] = Form(None),
    text: str = Form(..., min_length=1, max_length=MAX_WATERMARK_CHARS),
    position: Literal[POSITIONS] = Form("bottom-right"),  # type: ignore[valid-type]
    opacity: float = Form(0.5, ge=0.0, le=1.0),
    font_size: int = Form(36, ge=8, le=400),
    color: str = Form("#FFFFFF"),
    repeat: bool = Form(False),
):
    """Stamp your own text watermark onto a cleaned image."""
    try:
        rgb = parse_hex_color(color)
    except ValueError:
        raise HTTPException(400, "color must be #RRGGBB")
    data = await _read_input(file, key)
    return await _run_job(
        lambda: stamp_text(decode_image(data), text, position, opacity, font_size, rgb, repeat)
    )


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
    prompt: Optional[str] = Form(None, max_length=MAX_PROMPT_CHARS),
    preset: Optional[str] = Form(None),
    provider: Optional[Literal[PROVIDERS]] = Form(None),  # type: ignore[valid-type]
    quality: Literal["low", "medium", "high"] = Form("medium"),
):
    """Edit an image with Gemini or OpenAI using a preset (``remove_plate``,
    ``remove_watermark``, ...) or a free-form ``prompt``. Each call is billed by the provider."""
    if preset:
        if preset not in CLEANUP_PRESETS:
            raise HTTPException(400, f"Unknown preset. Choose from: {', '.join(CLEANUP_PRESETS)}")
        prompt = CLEANUP_PRESETS[preset]["prompt"]
    if not prompt or not prompt.strip():
        raise HTTPException(400, "Provide 'prompt' or 'preset'")

    editor = create_image_edit_provider(provider)
    if not editor:
        raise HTTPException(503, "No image edit provider configured. Set OPENAI_API_KEY or GEMINI_API_KEY in .env")

    image_bytes = await _read_input(file, key)
    try:
        decode_image(image_bytes)  # reject junk before paying for a provider call
    except ImageValidationError as e:
        raise HTTPException(400, str(e))
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
    providers = []
    for name in PROVIDERS:
        editor = create_image_edit_provider(name)
        if editor:
            providers.append({"name": name, "available": await editor.check_available(), "models": [editor.model]})
    return {"providers": providers}
