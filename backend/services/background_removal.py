"""Background removal with pluggable segmentation models.

``BG_REMOVAL_MODEL`` selects the backend:

* ``u2net`` (default), ``isnet-general-use``, ``birefnet-general`` ... - any
  model name supported by `rembg`, run through ONNX Runtime. No torch needed.
* ``birefnet`` - ZhengPeng7/BiRefNet through Hugging Face transformers (MIT).
* ``rmbg-2.0`` - briaai/RMBG-2.0 through transformers. Gated download that
  needs ``HF_TOKEN`` and licence acceptance on Hugging Face. The weights are
  CC BY-NC 4.0: NON-COMMERCIAL use only.

Every backend produces a soft mask that goes through the same edge refinement
(threshold, 1px erode, light blur) to remove the white halo that cut-outs of
studio shots usually get.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_TRANSFORMERS_MODELS = {
    "birefnet": "ZhengPeng7/BiRefNet",
    "rmbg-2.0": "briaai/RMBG-2.0",
}


def refine_mask(mask_np: np.ndarray) -> np.ndarray:
    """Threshold + 1px erode + light blur on a float mask in [0, 1].

    Raw model masks have semi-transparent edge pixels that still contain the
    original background colour; composited on anything else they show up as a
    halo. Cutting slightly inside the edge and re-antialiasing removes it.
    """
    mask_uint8 = (np.clip(mask_np, 0, 1) * 255).astype(np.uint8)
    _, binary = cv2.threshold(mask_uint8, 127, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded = cv2.erode(binary, kernel, iterations=1)
    result = cv2.GaussianBlur(eroded.astype(np.float32) / 255.0, (3, 3), 0.8)
    return np.clip(result, 0.0, 1.0)


class BackgroundRemovalService:
    def __init__(self, model_name: Optional[str] = None):
        self._requested = model_name
        self._session = None  # rembg session
        self._model = None  # transformers model
        self._device = None
        self._transform = None

    @property
    def model_name(self) -> str:
        if self._requested:
            return self._requested
        from config import get_settings
        return get_settings().bg_removal_model

    @property
    def is_loaded(self) -> bool:
        return self._session is not None or self._model is not None

    # -- loading --------------------------------------------------------------
    def load_model(self) -> None:
        name = self.model_name
        if name in _TRANSFORMERS_MODELS:
            self._load_transformers(name)
        else:
            from rembg import new_session
            logger.info("Loading rembg model '%s' (downloads to ~/.u2net on first use)...", name)
            # CPU provider keeps results reproducible across machines; ONNX Runtime's
            # CoreML provider (picked automatically on macOS) can stall while compiling.
            self._session = new_session(name, providers=["CPUExecutionProvider"])
        logger.info("Background removal model ready: %s", name)

    def _load_transformers(self, name: str) -> None:
        try:
            import torch
            from torchvision import transforms
            from transformers import AutoModelForImageSegmentation
        except ImportError as e:  # pragma: no cover - depends on optional deps
            raise RuntimeError(
                f"BG_REMOVAL_MODEL={name} needs the optional model dependencies: "
                "pip install -r backend/requirements-models.txt"
            ) from e
        from config import get_settings

        if torch.backends.mps.is_available():
            self._device = torch.device("mps")
        elif torch.cuda.is_available():
            self._device = torch.device("cuda")
        else:
            self._device = torch.device("cpu")

        repo = _TRANSFORMERS_MODELS[name]
        token = get_settings().hf_token or None
        if name == "rmbg-2.0" and not token:
            raise RuntimeError("BG_REMOVAL_MODEL=rmbg-2.0 requires HF_TOKEN (gated model, CC BY-NC 4.0)")
        logger.info("Loading %s on %s...", repo, self._device)
        self._model = AutoModelForImageSegmentation.from_pretrained(repo, trust_remote_code=True, token=token)
        self._model.to(self._device, dtype=torch.float32)
        self._model.eval()
        self._transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    # -- inference ------------------------------------------------------------
    def _predict_mask(self, original: Image.Image) -> np.ndarray:
        """Return a float mask in [0, 1] with the same size as ``original``."""
        w, h = original.size
        if self._session is not None:
            from rembg import remove
            mask = remove(original, session=self._session, only_mask=True)
            return np.asarray(mask.convert("L").resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0

        import torch
        tensor = self._transform(original).unsqueeze(0).to(self._device)
        with torch.no_grad():
            pred = self._model(tensor)[-1].sigmoid().cpu()
        mask_np = pred[0].squeeze().numpy()
        mask = Image.fromarray((mask_np * 255).astype(np.uint8), mode="L").resize((w, h), Image.LANCZOS)
        return np.asarray(mask, dtype=np.float32) / 255.0

    def remove_background(self, image_data: bytes) -> bytes:
        """Remove the background from encoded image bytes. Returns an RGBA PNG."""
        if not self.is_loaded:
            self.load_model()
        original = Image.open(io.BytesIO(image_data)).convert("RGB")
        refined = refine_mask(self._predict_mask(original))
        result = original.convert("RGBA")
        result.putalpha(Image.fromarray((refined * 255).astype(np.uint8), mode="L"))
        buf = io.BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()


bg_removal_service = BackgroundRemovalService()
