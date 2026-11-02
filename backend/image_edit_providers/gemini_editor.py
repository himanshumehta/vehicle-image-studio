"""Google Gemini provider for image editing."""
from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Optional
from PIL import Image

from .base import (
    REQUEST_TIMEOUT_S,
    VEHICLE_PHOTO_CONTEXT,
    ImageEditError,
    ImageEditProvider,
    ImageEditResult,
    provider_failure,
)


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
        source_img = Image.open(BytesIO(image_bytes))

        w, h = source_img.size
        if abs(w / h - 16 / 9) < 0.1:
            aspect = "16:9"
        elif abs(w / h - 4 / 3) < 0.1:
            aspect = "4:3"
        elif abs(w / h - 3 / 4) < 0.1:
            aspect = "3:4"
        else:
            aspect = "16:9"

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

        edited_bytes = None
        for part in response.parts:
            if part.inline_data is not None:
                edited_img = part.as_image()
                buf = BytesIO()
                edited_img.save(buf, format="PNG")
                edited_bytes = buf.getvalue()
                break

        if not edited_bytes:
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
