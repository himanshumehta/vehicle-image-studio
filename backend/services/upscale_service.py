"""Real-ESRGAN (x4plus) super-resolution on ONNX Runtime.

The ONNX file is produced from the official ``RealESRGAN_x4plus.pth`` release
by ``scripts/download_models.py`` (needs torch once, at setup). Inference is
tiled so memory stays flat regardless of input size.

Scales:
* 4x - one network pass.
* 2x - one 4x pass, then Lanczos down to 2x.
* 8x - two chained passes (4x, then 2x on the result).

Transparent inputs keep their alpha channel: RGB goes through the network and
the alpha is resized with Lanczos to the output size.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

MODEL_FILENAME = "realesrgan_x4plus.onnx"
DOWNLOAD_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "download_models.py")

TILE_SIZE = 256
TILE_PAD = 32
NET_SCALE = 4
SUPPORTED_SCALES = (2, 4, 8)


def model_path() -> str:
    from config import get_settings
    return os.path.join(get_settings().models_dir, MODEL_FILENAME)


class UpscaleService:
    def __init__(self):
        self._session = None

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def load_model(self) -> None:
        import onnxruntime as ort

        path = model_path()
        if not os.path.exists(path):
            logger.info("Real-ESRGAN ONNX model missing; running %s ...", DOWNLOAD_SCRIPT)
            result = subprocess.run(
                [sys.executable, DOWNLOAD_SCRIPT, "--only", "realesrgan"],
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0 or not os.path.exists(path):
                raise RuntimeError(
                    "Real-ESRGAN model not found and automatic download/conversion failed. "
                    "Run: pip install -r backend/requirements-models.txt && "
                    "python backend/scripts/download_models.py\n" + result.stderr[-2000:]
                )
        logger.info("Loading Real-ESRGAN ONNX model from %s", path)
        self._session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])

    def _run_tile(self, tile: np.ndarray) -> np.ndarray:
        name = self._session.get_inputs()[0].name
        return self._session.run(None, {name: tile})[0]

    def _upscale_array(self, img: np.ndarray) -> np.ndarray:
        """Tiled 4x upscale of an HWC uint8 RGB array."""
        h, w, c = img.shape
        out = np.zeros((h * NET_SCALE, w * NET_SCALE, c), dtype=np.float32)
        weight = np.zeros((h * NET_SCALE, w * NET_SCALE, 1), dtype=np.float32)
        padded = np.pad(img, ((TILE_PAD, TILE_PAD), (TILE_PAD, TILE_PAD), (0, 0)), mode="reflect")

        tiles_y = (h + TILE_SIZE - 1) // TILE_SIZE
        tiles_x = (w + TILE_SIZE - 1) // TILE_SIZE
        for ty in range(tiles_y):
            for tx in range(tiles_x):
                in_y, in_x = ty * TILE_SIZE, tx * TILE_SIZE
                in_h, in_w = min(TILE_SIZE, h - in_y), min(TILE_SIZE, w - in_x)
                tile = padded[in_y:in_y + in_h + 2 * TILE_PAD, in_x:in_x + in_w + 2 * TILE_PAD, :]
                tile_f = np.transpose(tile.astype(np.float32) / 255.0, (2, 0, 1))[None]
                res = np.transpose(np.squeeze(self._run_tile(tile_f), 0), (1, 2, 0))
                p = TILE_PAD * NET_SCALE
                res = res[p:p + in_h * NET_SCALE, p:p + in_w * NET_SCALE, :]
                oy, ox = in_y * NET_SCALE, in_x * NET_SCALE
                out[oy:oy + in_h * NET_SCALE, ox:ox + in_w * NET_SCALE, :] += res
                weight[oy:oy + in_h * NET_SCALE, ox:ox + in_w * NET_SCALE, :] += 1.0
        out /= np.maximum(weight, 1.0)
        return (np.clip(out, 0, 1) * 255).round().astype(np.uint8)

    def _pass(self, rgb: Image.Image, scale: int) -> Image.Image:
        result = Image.fromarray(self._upscale_array(np.asarray(rgb)), "RGB")
        if scale != NET_SCALE:
            result = result.resize((rgb.width * scale, rgb.height * scale), Image.LANCZOS)
        return result

    def upscale(self, image: Image.Image, scale: int = 4) -> Image.Image:
        """Upscale a PIL image by 2, 4 or 8. Returns RGB, or RGBA if the input had alpha."""
        if scale not in SUPPORTED_SCALES:
            raise ValueError(f"scale must be one of {SUPPORTED_SCALES}")
        if self._session is None:
            self.load_model()

        alpha: Optional[Image.Image] = None
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            image = image.convert("RGBA")
            alpha = image.getchannel("A")
        rgb = image.convert("RGB")

        logger.info("Upscaling %dx%d by %dx", rgb.width, rgb.height, scale)
        if scale == 8:
            result = self._pass(self._pass(rgb, 4), 2)
        else:
            result = self._pass(rgb, scale)

        if alpha is not None:
            result = result.convert("RGBA")
            result.putalpha(alpha.resize(result.size, Image.LANCZOS))
        logger.info("Upscale complete: %dx%d", result.width, result.height)
        return result


upscale_service = UpscaleService()
