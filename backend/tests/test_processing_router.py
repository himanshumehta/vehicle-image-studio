from unittest.mock import patch

import pytest
from PIL import Image

from tests.conftest import make_png


@pytest.fixture
def mock_models():
    with patch("routers.processing.bg_removal_service") as bg, \
         patch("routers.processing.upscale_service") as up:
        bg.remove_background.return_value = make_png(mode="RGBA")
        bg.is_loaded = True
        bg.model_name = "u2net"
        up.is_loaded = False
        up.upscale.side_effect = lambda img, scale=4: img.resize((img.width * scale, img.height * scale))
        yield {"bg": bg, "upscale": up}


@pytest.fixture
async def stored_key(client):
    resp = await client.post(
        "/api/images/import",
        data={"collection": "test"},
        files={"file": ("car.png", make_png(40, 20), "image/png")},
    )
    return resp.json()["key"]


@pytest.mark.asyncio
async def test_remove_background_json_key(client, mock_models, stored_key):
    resp = await client.post("/api/process/remove-background", json={"key": stored_key})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_remove_background_file(client, mock_models):
    resp = await client.post(
        "/api/process/remove-background", files={"file": ("a.png", make_png(), "image/png")}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_remove_background_missing_key(client, mock_models):
    resp = await client.post("/api/process/remove-background", json={"key": "vehicles/none.png"})
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("scale", [2, 4, 8])
async def test_upscale_scales(client, mock_models, stored_key, scale):
    resp = await client.post("/api/process/upscale", data={"key": stored_key, "scale": str(scale)})
    assert resp.status_code == 200
    import io
    out = Image.open(io.BytesIO(resp.content))
    assert out.size == (40 * scale, 20 * scale)


@pytest.mark.asyncio
async def test_upscale_rejects_bad_scale(client, mock_models, stored_key):
    resp = await client.post("/api/process/upscale", data={"key": stored_key, "scale": "3"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_studio_composite(client, mock_models, stored_key):
    resp = await client.post("/api/process/studio-composite", json={"key": stored_key})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mirror_and_crop(client, mock_models):
    resp = await client.post("/api/process/mirror", files={"file": ("a.png", make_png(), "image/png")})
    assert resp.status_code == 200
    resp = await client.post(
        "/api/process/crop",
        data={"crop_x": "10", "crop_y": "10", "crop_w": "50", "crop_h": "50"},
        files={"file": ("a.png", make_png(), "image/png")},
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/process/crop",
        data={"crop_x": "0", "crop_y": "0", "crop_w": "0", "crop_h": "0"},
        files={"file": ("a.png", make_png(), "image/png")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_no_input_is_400(client, mock_models):
    resp = await client.post("/api/process/mirror")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_enhance_keeps_size(client, mock_models, stored_key):
    import io
    resp = await client.post("/api/process/enhance", data={"key": stored_key})
    assert resp.status_code == 200
    assert Image.open(io.BytesIO(resp.content)).size == (40, 20)


@pytest.mark.asyncio
async def test_llm_edit_without_keys_is_503(client, stored_key):
    resp = await client.post("/api/process/llm-edit", data={"key": stored_key, "preset": "remove_plate"})
    assert resp.status_code == 503
    resp = await client.get("/api/process/llm-edit/providers")
    assert resp.json() == {"providers": []}


@pytest.mark.asyncio
async def test_llm_edit_presets(client):
    resp = await client.get("/api/process/llm-edit/presets")
    ids = {p["id"] for p in resp.json()}
    assert {"remove_plate", "remove_watermark"} <= ids


@pytest.mark.asyncio
async def test_health(client, mock_models):
    resp = await client.get("/api/process/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
