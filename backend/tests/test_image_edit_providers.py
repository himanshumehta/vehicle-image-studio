"""Provider adapters, exercised with stub clients: no network, no API keys."""
import base64
import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from image_edit_providers import _build, create_image_edit_provider
from image_edit_providers.base import ImageEditError
from image_edit_providers.openai_editor import OpenAIImageEditor
from tests.conftest import make_png


def _settings(**overrides):
    base = dict(
        openai_api_key="", openai_image_model="gpt-image-1",
        gemini_api_key="", gemini_image_model="gemini-2.5-flash-image",
        image_edit_provider="openai",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_factory_needs_a_key_and_falls_back(monkeypatch):
    assert _build("openai", _settings()) is None
    gemini_only = _settings(gemini_api_key="test-key")
    monkeypatch.setattr("config.get_settings", lambda: gemini_only)
    editor = create_image_edit_provider()
    assert editor is not None and editor.name == "gemini"
    assert create_image_edit_provider("openai") is None


def _editor_with(edit):
    editor = OpenAIImageEditor(api_key="test-key")
    editor._client = MagicMock()
    editor._client.images.edit.side_effect = edit
    return editor


async def test_openai_success_reports_cost_and_size():
    out = make_png(30, 20)
    editor = _editor_with(lambda **kw: SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(out).decode())]))
    result = await editor.edit_image(make_png(60, 40), "blank the plate", quality="low")
    assert (result.width, result.height, result.provider) == (30, 20, "openai")
    assert result.cost_estimate_usd == pytest.approx(0.009)
    kwargs = editor._client.images.edit.call_args.kwargs
    assert kwargs["size"] == "1536x1024" and kwargs["quality"] == "low"


async def test_openai_errors_are_short_and_classified():
    def boom(**kw):
        raise RuntimeError("Rate limit reached for org-123 using key sk-live-abc")

    with pytest.raises(ImageEditError) as info:
        await _editor_with(boom).edit_image(make_png(), "x")
    assert info.value.retryable is True
    assert "sk-live" not in str(info.value) and "org-123" not in str(info.value)


# --- Gemini: responses built by the real SDK from API-shaped JSON ---------------


def _gemini_with(response_json, seen=None):
    from google.genai import types

    from image_edit_providers.gemini_editor import GeminiImageEditor

    response = types.GenerateContentResponse.model_validate(response_json)

    def generate_content(model, contents, config):
        if seen is not None:
            seen.append(config.image_config.aspect_ratio)
        return response

    editor = GeminiImageEditor(api_key="test-key")
    editor._client = MagicMock()
    editor._client.models.generate_content.side_effect = generate_content
    return editor


def _gemini_image_json(png: bytes) -> dict:
    parts = [{"text": "done"}, {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png).decode()}}]
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}]}


async def test_gemini_success_returns_the_model_pixels_as_png():
    out = make_png(30, 20, color=(10, 200, 30))
    result = await _gemini_with(_gemini_image_json(out)).edit_image(make_png(60, 40), "blank the plate")
    assert (result.width, result.height, result.provider) == (30, 20, "gemini")
    assert result.image_bytes[:4] == b"\x89PNG"
    assert Image.open(io.BytesIO(result.image_bytes)).convert("RGB").getpixel((5, 5)) == (10, 200, 30)


async def test_gemini_blocked_response_is_a_clean_error():
    blocked = {"candidates": [{"finishReason": "PROHIBITED_CONTENT"}]}
    with pytest.raises(ImageEditError) as info:
        await _gemini_with(blocked).edit_image(make_png(), "x")
    assert info.value.retryable is False


async def test_gemini_requests_common_aspect_ratios():
    seen = []
    editor = _gemini_with(_gemini_image_json(make_png(16, 9)), seen)
    for w, h in ((1920, 1080), (1600, 1200)):
        await editor.edit_image(make_png(w, h), "x")
    assert seen == ["16:9", "4:3"]


async def test_gemini_keeps_3_2_inputs_at_3_2():
    seen = []
    await _gemini_with(_gemini_image_json(make_png(16, 9)), seen).edit_image(make_png(1200, 800), "x")
    assert seen == ["3:2"]


async def test_gemini_requests_the_nearest_supported_ratio_for_portrait_and_square():
    seen = []
    editor = _gemini_with(_gemini_image_json(make_png(16, 9)), seen)
    for w, h in ((800, 1200), (1024, 1024), (1080, 1920)):
        await editor.edit_image(make_png(w, h), "x")
    assert seen == ["2:3", "1:1", "9:16"]


def _jpeg_with_orientation(width, height, orientation):
    img = Image.new("RGB", (width, height), (10, 20, 30))
    exif = img.getexif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


async def test_gemini_honours_exif_orientation():
    # Stored landscape 1200x800, tagged "rotate 90": a viewer sees an 800x1200 portrait.
    seen = []
    await _gemini_with(_gemini_image_json(make_png(16, 9)), seen).edit_image(
        _jpeg_with_orientation(1200, 800, 6), "x")
    assert seen == ["2:3"]


def test_nearest_ratio_is_symmetric_and_picks_openai_square_for_near_square():
    from image_edit_providers.base import GEMINI_ASPECT_RATIOS, OPENAI_SIZES, nearest_ratio

    assert nearest_ratio(1200, 800, GEMINI_ASPECT_RATIOS) == "3:2"
    assert nearest_ratio(800, 1200, GEMINI_ASPECT_RATIOS) == "2:3"
    assert nearest_ratio(1100, 1000, OPENAI_SIZES) == "1024x1024"
    assert nearest_ratio(1600, 1000, OPENAI_SIZES) == "1536x1024"
