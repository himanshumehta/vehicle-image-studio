"""Provider adapters, exercised with stub clients: no network, no API keys."""
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
