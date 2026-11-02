"""Factory for image-edit (inpainting) providers.

Adding a provider = subclass ``ImageEditProvider`` and register it in ``_build``.
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import ImageEditProvider

logger = logging.getLogger(__name__)

PROVIDERS = ("openai", "gemini")


def _build(name: str, settings) -> Optional[ImageEditProvider]:
    if name == "openai":
        if not settings.openai_api_key:
            return None
        from .openai_editor import OpenAIImageEditor
        return OpenAIImageEditor(api_key=settings.openai_api_key, model=settings.openai_image_model)
    if name == "gemini":
        if not settings.gemini_api_key:
            return None
        from .gemini_editor import GeminiImageEditor
        return GeminiImageEditor(api_key=settings.gemini_api_key, model=settings.gemini_image_model)
    logger.warning("Unknown image edit provider: %s", name)
    return None


def create_image_edit_provider(provider_name: Optional[str] = None) -> Optional[ImageEditProvider]:
    """Return the requested provider, or (when none is named) the configured
    default, falling back to any other provider that has an API key."""
    from config import get_settings

    settings = get_settings()
    if provider_name:
        return _build(provider_name, settings)
    preferred = settings.image_edit_provider
    order = [preferred] + [p for p in PROVIDERS if p != preferred]
    for name in order:
        editor = _build(name, settings)
        if editor:
            return editor
    return None
