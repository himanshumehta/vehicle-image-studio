import numpy as np
import pytest
from PIL import Image

from services.upscale_service import UpscaleService


class _FakeInput:
    name = "input"


class FakeSession:
    """Stands in for the ONNX model: nearest-neighbour 4x on an NCHW tile."""

    def get_inputs(self):
        return [_FakeInput()]

    def run(self, _outputs, feeds):
        x = feeds["input"]
        return [x.repeat(4, axis=2).repeat(4, axis=3)]


@pytest.fixture
def service():
    s = UpscaleService()
    s._session = FakeSession()
    return s


@pytest.mark.parametrize("scale", [2, 4, 8])
def test_output_size(service, scale):
    img = Image.new("RGB", (300, 70), (10, 200, 30))  # > one tile wide
    out = service.upscale(img, scale=scale)
    assert out.size == (300 * scale, 70 * scale)
    assert out.mode == "RGB"


def test_tiling_is_seamless(service):
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, size=(300, 520, 3), dtype=np.uint8)
    out = np.asarray(service.upscale(Image.fromarray(arr), scale=4))
    expected = arr.repeat(4, axis=0).repeat(4, axis=1)
    assert np.abs(out.astype(int) - expected.astype(int)).max() <= 1


def test_alpha_preserved(service):
    img = Image.new("RGBA", (40, 30), (255, 0, 0, 0))
    img.paste((0, 0, 255, 255), (10, 10, 30, 20))
    out = service.upscale(img, scale=2)
    assert out.mode == "RGBA"
    assert out.size == (80, 60)
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((40, 30))[3] == 255


def test_rejects_unsupported_scale(service):
    with pytest.raises(ValueError):
        service.upscale(Image.new("RGB", (8, 8)), scale=3)
