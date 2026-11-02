"""Regression tests for the hardening in http_security.py, storage keys, uploads and job limits."""
import asyncio
import threading
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI, File, UploadFile

from config import MAX_REQUEST_BYTES, MAX_UPLOAD_BYTES
from http_security import BodySizeLimitMiddleware, is_cross_site_write
from services.background_removal import _TRANSFORMERS_MODELS
from services.errors import ImageTooLargeError
from services.jobs import JobLimiter, ServerBusyError
from services.storage import InvalidKeyError, validate_key
from services.upscale_service import check_upscale_size
from tests.conftest import make_png


# --- storage keys and served files -------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["/etc/passwd.png", "../x.png", "vehicles/../../x.png", "vehicles//x.png", "vehicles/./x.png",
     "vehicles\\x.png", "vehicles/x\x00.png", "vehicles/x.html", "vehicles/x.svg", "", "a" * 600 + ".png"],
)
def test_validate_key_rejects(key):
    with pytest.raises(InvalidKeyError):
        validate_key(key)


def test_validate_key_accepts_nested_image_keys():
    assert validate_key("vehicles/my-cars/Red Hatch.JPG") == "vehicles/my-cars/Red Hatch.JPG"


async def test_cannot_store_html_for_the_file_server(client):
    """Stored XSS: an .html key would be served as text/html on the app's own origin."""
    resp = await client.post(
        "/api/images/upload",
        data={"key": "vehicles/x/evil.html"},
        files={"file": ("evil.png", make_png(), "image/png")},
    )
    assert resp.status_code == 400
    assert (await client.get("/api/files/vehicles/x/evil.html")).status_code == 404


async def test_upload_and_import_reject_non_image_bytes(client):
    payload = b"<html><script>alert(document.domain)</script></html>"
    resp = await client.post(
        "/api/images/upload",
        data={"key": "vehicles/x/fake.png"},
        files={"file": ("fake.png", payload, "image/png")},
    )
    assert resp.status_code == 400
    resp = await client.post("/api/images/import", files={"file": ("fake.png", payload, "image/png")})
    assert resp.status_code == 400


async def test_import_takes_extension_from_content_not_filename(client):
    resp = await client.post(
        "/api/images/import",
        data={"collection": "sec"},
        files={"file": ("photo.jpg", make_png(8, 8), "image/jpeg")},
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "vehicles/sec/photo.png"
    served = await client.get(resp.json()["url"])
    assert served.headers["content-type"] == "image/png"
    await client.delete(f"/api/images/detail/{resp.json()['key']}")


async def test_api_responses_carry_security_headers(client):
    resp = await client.get("/api/images")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "sandbox" in resp.headers["content-security-policy"]


async def test_errors_do_not_leak_internals(client):
    with patch("routers.processing.bg_removal_service") as bg:
        bg.remove_background.side_effect = RuntimeError("/srv/secret/models/u2net.onnx exploded")
        resp = await client.post("/api/process/remove-background", files={"file": ("a.png", make_png(), "image/png")})
    assert resp.status_code == 500
    assert "/srv/secret" not in resp.text


# --- list / form parameter bounds --------------------------------------------


@pytest.mark.parametrize("params", [{"max_keys": "100000"}, {"max_keys": "0"}, {"continuation_token": "abc"}])
async def test_list_images_bounds(client, params):
    assert (await client.get("/api/images", params=params)).status_code == 422


@pytest.mark.parametrize(
    "fields",
    [{"text": "x", "font_size": "100000"}, {"text": "x" * 500}, {"text": "x", "position": "nowhere"},
     {"text": "x", "opacity": "5"}],
)
async def test_watermark_bounds(client, fields):
    resp = await client.post("/api/process/watermark", data=fields, files={"file": ("a.png", make_png(), "image/png")})
    assert resp.status_code == 422


@pytest.mark.parametrize("fields", [{"prompt": "x" * 5000}, {"prompt": "x", "provider": "acme"}, {"prompt": "x", "quality": "ultra"}])
async def test_llm_edit_bounds(client, fields):
    resp = await client.post("/api/process/llm-edit", data=fields, files={"file": ("a.png", make_png(), "image/png")})
    assert resp.status_code == 422


# --- request size -------------------------------------------------------------


async def test_declared_body_over_limit_is_413(client):
    resp = await client.post(
        "/api/images/import",
        content=b"x",
        headers={"content-length": str(MAX_REQUEST_BYTES + 1), "content-type": "multipart/form-data; boundary=x"},
    )
    assert resp.status_code == 413


async def test_single_upload_over_limit_is_413(client):
    big = b"\0" * (MAX_UPLOAD_BYTES + 1)
    resp = await client.post("/api/images/import", files={"file": ("big.png", big, "image/png")})
    assert resp.status_code == 413


async def test_streamed_body_without_length_is_cut_off():
    app = FastAPI()

    @app.post("/up")
    async def up(file: UploadFile = File(...)):
        return {"n": len(await file.read())}

    limited = BodySizeLimitMiddleware(app, max_bytes=1024)
    body = b"--b\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a\"\r\n\r\n" + b"x" * 5000 + b"\r\n--b--\r\n"

    async def chunks():
        for i in range(0, len(body), 256):
            yield body[i:i + 256]

    transport = httpx.ASGITransport(app=limited)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/up", content=chunks(), headers={"content-type": "multipart/form-data; boundary=b"})
    assert resp.status_code == 413


# --- cross-site writes and Host header ---------------------------------------


@pytest.mark.parametrize(
    ("method", "headers", "blocked"),
    [
        ("POST", {"sec-fetch-site": "cross-site", "origin": "https://evil.example"}, True),
        ("POST", {"origin": "https://evil.example", "host": "localhost:8000"}, True),
        ("DELETE", {"sec-fetch-site": "cross-site"}, True),
        ("POST", {"sec-fetch-site": "same-origin", "origin": "http://localhost:3000"}, False),
        ("POST", {"sec-fetch-site": "cross-site", "origin": "http://localhost:3000"}, False),  # allow-listed
        ("POST", {"origin": "http://localhost:8000", "host": "localhost:8000"}, False),
        ("POST", {}, False),  # curl / scripts
        ("GET", {"sec-fetch-site": "cross-site"}, False),
    ],
)
def test_cross_site_write_rule(method, headers, blocked):
    assert is_cross_site_write(method, headers, ["http://localhost:3000"]) is blocked


async def test_cross_site_post_is_refused(client):
    resp = await client.post(
        "/api/images/upload",
        data={"key": "vehicles/x/a.png"},
        files={"file": ("a.png", make_png(), "image/png")},
        headers={"sec-fetch-site": "cross-site", "origin": "https://evil.example"},
    )
    assert resp.status_code == 403


async def test_unknown_host_header_is_refused(client):
    """DNS rebinding: a page on evil.example resolved to 127.0.0.1 still sends Host: evil.example."""
    resp = await client.get("/api/images", headers={"host": "evil.example"})
    assert resp.status_code == 400


async def test_cors_does_not_allow_credentials(client):
    resp = await client.options(
        "/api/images",
        headers={"origin": "http://localhost:3000", "access-control-request-method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" not in resp.headers


# --- heavy-job limits ---------------------------------------------------------


def test_upscale_size_limit():
    check_upscale_size(320, 213, 8, limit=25_000_000)  # the README's 8x demo fits
    with pytest.raises(ImageTooLargeError):
        check_upscale_size(1200, 800, 8, limit=25_000_000)
    with pytest.raises(ImageTooLargeError):
        check_upscale_size(2000, 2000, 2, limit=25_000_000)


async def test_upscale_over_limit_is_413_before_running_the_model(client):
    with patch("routers.processing.upscale_service") as up:
        resp = await client.post(
            "/api/process/upscale",
            data={"scale": "8"},
            files={"file": ("a.png", make_png(400, 300), "image/png")},
        )
        assert resp.status_code == 413
        up.upscale.assert_not_called()


async def test_job_limiter_rejects_when_all_slots_are_busy():
    limiter = JobLimiter(max_concurrent=1, queue_timeout_s=0.05)
    started = threading.Event()

    def slow():
        started.set()
        time.sleep(0.3)
        return "done"

    first = asyncio.ensure_future(limiter.run(slow))
    await asyncio.get_running_loop().run_in_executor(None, started.wait)
    with pytest.raises(ServerBusyError):
        await limiter.run(lambda: "second")
    assert await first == "done"
    assert await limiter.run(lambda: "third") == "third"  # the slot is released


async def test_busy_server_answers_503_with_retry_after(client):
    busy = JobLimiter(max_concurrent=1, queue_timeout_s=0.01)
    busy._slots.acquire()  # occupy the only slot
    try:
        with patch("routers.processing.get_job_limiter", return_value=busy):
            resp = await client.post("/api/process/mirror", files={"file": ("a.png", make_png(), "image/png")})
    finally:
        busy._slots.release()
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "1"


# --- model supply chain ------------------------------------------------------


def test_remote_code_models_are_pinned_to_a_commit():
    for repo, revision in _TRANSFORMERS_MODELS.values():
        assert len(revision) == 40 and int(revision, 16) >= 0, repo
