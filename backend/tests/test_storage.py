import pytest

from services.storage import LocalStorage, StorageError, derive_nobg_key


def test_roundtrip_and_listing(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.upload_image("vehicles/cars/a.jpg", b"jpgdata", "image/jpeg")
    s.upload_image("vehicles/cars/a-nobg.png", b"pngdata")
    s.upload_image("vehicles/bikes/b.png", b"pngdata")

    assert s.download_image("vehicles/cars/a.jpg") == b"jpgdata"
    listing = s.list_images(prefix="vehicles/cars/")
    assert [i["key"] for i in listing["images"]] == ["vehicles/cars/a.jpg"]
    assert listing["images"][0]["has_nobg"] is True
    assert listing["images"][0]["url"] == "/api/files/vehicles/cars/a.jpg"

    groups = {g["slug"]: g["image_count"] for g in s.list_brand_prefixes()}
    assert groups == {"cars": 1, "bikes": 1}


def test_pagination(tmp_path):
    s = LocalStorage(str(tmp_path))
    for i in range(5):
        s.upload_image(f"vehicles/x/{i}.png", b"x")
    first = s.list_images(max_keys=2)
    assert len(first["images"]) == 2 and first["next_token"] == "2"
    last = s.list_images(max_keys=2, continuation_token="4")
    assert len(last["images"]) == 1 and last["next_token"] == ""


def test_path_traversal_rejected(tmp_path):
    s = LocalStorage(str(tmp_path / "root"))
    with pytest.raises(StorageError):
        s.upload_image("../escape.png", b"x")
    assert s.key_exists("../../etc/passwd") is False


def test_delete(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.upload_image("vehicles/x/a.png", b"x")
    s.delete_image("vehicles/x/a.png")
    assert not s.key_exists("vehicles/x/a.png")


def test_derive_nobg_key():
    assert derive_nobg_key("vehicles/a/b.jpg") == "vehicles/a/b-nobg.png"
