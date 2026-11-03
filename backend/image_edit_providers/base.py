"""Abstract base for LLM-based image editing providers."""
from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Upper bound on one provider call; image edits normally finish well inside this.
REQUEST_TIMEOUT_S = 120


@dataclass
class ImageEditResult:
    image_bytes: bytes
    width: int
    height: int
    provider: str
    model: str
    prompt_used: str
    cost_estimate_usd: Optional[float]


class ImageEditProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def model(self) -> str:
        return getattr(self, "_model", "")

    @abstractmethod
    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        quality: str = "medium",
        size: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> ImageEditResult:
        ...

    @abstractmethod
    async def check_available(self) -> bool:
        ...


class ImageEditError(Exception):
    def __init__(self, message: str, provider: str, retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


def provider_failure(provider: str, exc: Exception, retry_markers: tuple) -> ImageEditError:
    """Log the provider's full error server-side; return a short, client-safe ImageEditError."""
    detail = str(exc).lower()
    retryable = any(marker in detail for marker in retry_markers)
    logger.warning("%s image edit failed: %s: %s", provider, type(exc).__name__, exc)
    reason = "rate limited or timed out, retry later" if retryable else type(exc).__name__
    return ImageEditError(f"{provider} image edit failed ({reason})", provider=provider, retryable=retryable)


# Output aspect ratios the Gemini image models accept.
GEMINI_ASPECT_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
# Output sizes the OpenAI image edit endpoint accepts.
OPENAI_SIZES = ("1024x1024", "1536x1024", "1024x1536")


def upright(img: Image.Image) -> Image.Image:
    """``img`` rotated/flipped as its EXIF orientation says, i.e. as a viewer sees it."""
    return ImageOps.exif_transpose(img) if img.getexif().get(0x0112, 1) != 1 else img


def nearest_ratio(width: int, height: int, choices) -> str:
    """The ``"W:H"`` (or ``"WxH"``) choice closest to width/height, compared on a log scale
    so that a ratio and its reciprocal are equally far from 1:1."""
    target = math.log(width / height)

    def distance(choice: str) -> float:
        w, h = (float(x) for x in re.split(r"[:x]", choice))
        return abs(math.log(w / h) - target)

    return min(choices, key=distance)


VEHICLE_PHOTO_CONTEXT = (
    "You are editing a professional vehicle/motorcycle photograph. "
    "Preserve all vehicle details, reflections, and shadows precisely. "
    "Only change what the user explicitly asks to change. "
    "Output photorealistic results suitable for an automotive listing."
)


# Clean-up tasks the studio exposes as one-click presets. The image-edit model
# performs the inpainting; the prompt constrains it to the target region.
CLEANUP_PRESETS = {
    "remove_plate": {
        "label": "Remove number plate",
        "prompt": (
            "Remove all characters from the vehicle's number plate(s) so the plate is blank, "
            "keeping the plate's shape, colour, mounting, lighting and perspective. "
            "Do not change anything else in the image."
        ),
    },
    "remove_watermark": {
        "label": "Remove watermark",
        "prompt": (
            "Remove any watermark, logo overlay or semi-transparent text stamped over the photo, "
            "reconstructing the vehicle and background underneath. "
            "Do not change anything else in the image."
        ),
    },
    "remove_plate_and_watermark": {
        "label": "Remove plate + watermark",
        "prompt": (
            "Blank out the characters on the vehicle's number plate(s) and remove any watermark "
            "or overlaid text, reconstructing what is underneath. "
            "Do not change anything else in the image."
        ),
    },
}
