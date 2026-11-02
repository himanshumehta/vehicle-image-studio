import io

import numpy as np
from PIL import Image

from services.background_removal import BackgroundRemovalService, refine_mask


def test_refine_mask_binarises_and_shrinks():
    mask = np.zeros((20, 20), dtype=np.float32)
    mask[5:15, 5:15] = 0.9
    mask[4, 5:15] = 0.3  # soft fringe row
    out = refine_mask(mask)
    assert out.shape == mask.shape
    assert out[10, 10] > 0.99
    assert out[4, 10] < 0.05  # fringe removed
    assert out.min() >= 0 and out.max() <= 1


def test_remove_background_applies_mask():
    svc = BackgroundRemovalService(model_name="fake")
    svc._session = object()  # mark as loaded

    def fake_predict(img):
        m = np.zeros((img.height, img.width), dtype=np.float32)
        m[:, : img.width // 2] = 1.0
        return m

    svc._predict_mask = fake_predict
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), (200, 10, 10)).save(buf, format="JPEG")
    out = Image.open(io.BytesIO(svc.remove_background(buf.getvalue())))
    assert out.mode == "RGBA" and out.size == (40, 20)
    assert out.getpixel((5, 10))[3] == 255
    assert out.getpixel((35, 10))[3] == 0
