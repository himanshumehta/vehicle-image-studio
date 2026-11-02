from PIL import Image
import io
from utils.image_helpers import bytes_to_pil, pil_to_bytes


def test_bytes_to_pil():
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    result = bytes_to_pil(data)
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
    restored = bytes_to_pil(data)
    assert restored.size == original.size
    assert restored.mode == original.mode
    # Check a pixel matches
    assert restored.getpixel((25, 25)) == (100, 150, 200)


def test_rgba_roundtrip():
    original = Image.new("RGBA", (20, 20), (100, 150, 200, 128))
    data = pil_to_bytes(original, fmt="PNG")
    restored = bytes_to_pil(data)
    assert restored.mode == "RGBA"
    assert restored.getpixel((10, 10)) == (100, 150, 200, 128)


def test_pil_to_bytes_returns_bytes():
    img = Image.new("RGB", (5, 5))
    result = pil_to_bytes(img)
    assert isinstance(result, bytes)
    assert len(result) > 0
