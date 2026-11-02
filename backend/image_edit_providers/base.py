"""Abstract base for LLM-based image editing providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


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
