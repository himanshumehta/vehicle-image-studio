from PIL import Image
import io
from utils.image_helpers import decode_image, pil_to_bytes


def test_decode_image():
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    result = decode_image(data)
    assert result.size == (10, 10)
    assert result.mode == "RGB"


def test_pil_to_bytes_png():
    img = Image.new("RGB", (10, 10), (0, 255, 0))
    data = pil_to_bytes(img, fmt="PNG")
    assert data[:4] == b"\x89PNG"


def test_pil_to_bytes_jpeg():
    img = Image.new("RGB", (10, 10), (0, 0, 255))
    data = pil_to_bytes(img, fmt="JPEG")
    assert data[:2] == b"\xff\xd8"


def test_roundtrip():
    original = Image.new("RGB", (50, 50), (100, 150, 200))
    data = pil_to_bytes(original, fmt="PNG")
    restored = decode_image(data)
    assert restored.size == original.size
    assert restored.mode == original.mode
    # Check a pixel matches
    assert restored.getpixel((25, 25)) == (100, 150, 200)


def test_rgba_roundtrip():
    original = Image.new("RGBA", (20, 20), (100, 150, 200, 128))
    data = pil_to_bytes(original, fmt="PNG")
    restored = decode_image(data)
    assert restored.mode == "RGBA"
    assert restored.getpixel((10, 10)) == (100, 150, 200, 128)


def test_pil_to_bytes_returns_bytes():
    img = Image.new("RGB", (5, 5))
    result = pil_to_bytes(img)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_decode_rejects_non_images():
    import pytest
    from utils.image_helpers import ImageValidationError

    with pytest.raises(ImageValidationError):
        decode_image(b"<html><script>alert(1)</script></html>")


def test_decode_rejects_unlisted_formats():
    import pytest
    from utils.image_helpers import ImageValidationError

    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="GIF")
    with pytest.raises(ImageValidationError, match="Unsupported"):
        decode_image(buf.getvalue())


def test_decode_checks_pixel_count_before_decompressing(monkeypatch):
    """A tiny file that declares huge dimensions (decompression bomb) is refused from its header."""
    import pytest
    import utils.image_helpers as helpers

    monkeypatch.setattr(helpers, "max_image_pixels", lambda: 10_000)
    bomb = pil_to_bytes(Image.new("L", (200, 200)), fmt="PNG")  # 40,000 px, compresses to ~200 bytes
    assert len(bomb) < 1000
    with pytest.raises(helpers.ImageValidationError, match="limit"):
        decode_image(bomb)
