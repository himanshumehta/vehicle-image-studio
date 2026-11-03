"""Google Gemini provider for image editing."""
from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Optional
from PIL import Image

from .base import (
    GEMINI_ASPECT_RATIOS,
    REQUEST_TIMEOUT_S,
    VEHICLE_PHOTO_CONTEXT,
    ImageEditError,
    ImageEditProvider,
    ImageEditResult,
    nearest_ratio,
    provider_failure,
    upright,
)

logger = logging.getLogger(__name__)


class GeminiImageEditor(ImageEditProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-image"):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000),  # milliseconds
            )
        return self._client

    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        quality: str = "medium",
        size: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> ImageEditResult:
        from google.genai import types

        client = self._get_client()
        # Send the photo the way the user sees it (phone JPEGs are often stored sideways
        # with an EXIF orientation tag) and ask for the closest supported aspect ratio.
        source_img = upright(Image.open(BytesIO(image_bytes)))
        aspect = nearest_ratio(*source_img.size, GEMINI_ASPECT_RATIOS)

        context = system_context or VEHICLE_PHOTO_CONTEXT
        full_prompt = f"{context}\n\nUser request: {prompt}"

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self._model,
                contents=[full_prompt, source_img],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect),
                ),
            )
        except Exception as e:
            raise provider_failure("gemini", e, ("quota", "rate", "429", "timeout", "timed out")) from e

        # A blocked or empty response has no parts at all; the finish reason goes to the log only.
        parts = response.parts or []
        edited_bytes = None
        for part in parts:
            if part.inline_data is not None and part.inline_data.data:
                # Re-encode the returned bytes as PNG. part.as_image() is not used: in the
                # SDK it returns google.genai.types.Image, which has no PIL-style save().
                edited_img = Image.open(BytesIO(part.inline_data.data))
                buf = BytesIO()
                edited_img.save(buf, format="PNG")
                edited_bytes = buf.getvalue()
                break

        if not edited_bytes:
            candidates = response.candidates or []
            finish = candidates[0].finish_reason if candidates else None
            logger.warning("gemini returned no image (finish_reason=%s)", finish)
            raise ImageEditError(
                "Gemini returned no image in response",
                provider="gemini",
                retryable=False,
            )

        out_img = Image.open(BytesIO(edited_bytes))
        return ImageEditResult(
            image_bytes=edited_bytes,
            width=out_img.width,
            height=out_img.height,
            provider="gemini",
            model=self._model,
            prompt_used=full_prompt,
            cost_estimate_usd=0.039,
        )

    async def check_available(self) -> bool:
        try:
            self._get_client()
            return bool(self._api_key)
        except Exception:
            return False
