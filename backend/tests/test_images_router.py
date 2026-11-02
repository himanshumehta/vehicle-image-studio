import pytest

from tests.conftest import make_png


@pytest.mark.asyncio
async def test_import_list_detail_serve_delete(client):
    png = make_png(20, 10)
    resp = await client.post(
        "/api/images/import",
        data={"collection": "My Cars"},
        files={"file": ("Red Hatch.png", png, "image/png")},
    )
    assert resp.status_code == 200
    key = resp.json()["key"]
    assert key == "vehicles/my-cars/red-hatch.png"

    resp = await client.get("/api/images/brands")
    assert any(b["slug"] == "my-cars" for b in resp.json()["brands"])

    resp = await client.get("/api/images", params={"prefix": "vehicles/my-cars/"})
    assert resp.json()["count"] == 1

    resp = await client.get(f"/api/images/detail/{key}")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["nobg_variant"]["exists"] is False

    resp = await client.get(meta["url"])
    assert resp.status_code == 200
    assert resp.content == png

    resp = await client.delete(f"/api/images/detail/{key}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/images/detail/{key}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_save_edited_image(client):
    resp = await client.post(
        "/api/images/upload",
        data={"key": "vehicles/edits/out.png"},
        files={"file": ("out.png", make_png(), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "vehicles/edits/out.png"


@pytest.mark.asyncio
async def test_save_rejects_traversal(client):
    resp = await client.post(
        "/api/images/upload",
        data={"key": "../../evil.png"},
        files={"file": ("out.png", make_png(), "image/png")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_missing_file_404(client):
    resp = await client.get("/api/files/vehicles/nope.png")
    assert resp.status_code == 404
