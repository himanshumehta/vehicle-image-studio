"""OpenAI GPT Image provider for image editing."""
from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from typing import Optional
from PIL import Image

from .base import REQUEST_TIMEOUT_S, VEHICLE_PHOTO_CONTEXT, ImageEditProvider, ImageEditResult, provider_failure

QUALITY_MAP = {"low": "low", "medium": "medium", "high": "high"}
COST_ESTIMATES = {"low": 0.009, "medium": 0.034, "high": 0.133}


class OpenAIImageEditor(ImageEditProvider):
    def __init__(self, api_key: str, model: str = "gpt-image-1"):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, timeout=REQUEST_TIMEOUT_S, max_retries=1)
        return self._client

    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        quality: str = "medium",
        size: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> ImageEditResult:
        client = self._get_client()

        if not size:
            img = Image.open(BytesIO(image_bytes))
            w, h = img.size
            if w > h:
                size = "1536x1024"
            elif h > w:
                size = "1024x1536"
            else:
                size = "1024x1024"

        context = system_context or VEHICLE_PHOTO_CONTEXT
        full_prompt = f"{context}\n\nUser request: {prompt}"

        try:
            result = await asyncio.to_thread(
                client.images.edit,
                model=self._model,
                image=BytesIO(image_bytes),
                prompt=full_prompt,
                quality=QUALITY_MAP.get(quality, "medium"),
                size=size,
            )
        except Exception as e:
            raise provider_failure("openai", e, ("rate_limit", "rate limit", "timeout", "timed out")) from e

        edited_bytes = base64.b64decode(result.data[0].b64_json)
        edited_img = Image.open(BytesIO(edited_bytes))

        return ImageEditResult(
            image_bytes=edited_bytes,
            width=edited_img.width,
            height=edited_img.height,
            provider="openai",
            model=self._model,
            prompt_used=full_prompt,
            cost_estimate_usd=COST_ESTIMATES.get(quality, 0.034),
        )

    async def check_available(self) -> bool:
        try:
            self._get_client()
            return bool(self._api_key)
        except Exception:
            return False
