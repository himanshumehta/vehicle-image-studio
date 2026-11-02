"""Decoding untrusted image bytes, and encoding results.

Every image that arrives over HTTP goes through :func:`decode_image`, which only
accepts JPEG, PNG and WebP, checks the pixel count from the header before any
pixel data is decompressed, and turns Pillow's decompression-bomb warning into
an error.
"""
from __future__ import annotations

import io
import warnings

from PIL import Image, UnidentifiedImageError

# Pillow format name -> (MIME type, file extension) of the formats we accept.
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class ImageValidationError(ValueError):
    """The bytes are not an acceptable image. The message is safe to show to clients."""


def max_image_pixels() -> int:
    from config import get_settings

    return get_settings().max_image_pixels


def decode_image(data: bytes) -> Image.Image:
    """Decode untrusted bytes into a fully loaded PIL image, or raise ImageValidationError."""
    limit = max_image_pixels()
    Image.MAX_IMAGE_PIXELS = limit  # Pillow's own bomb check uses the same limit
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            img = Image.open(io.BytesIO(data))
            if img.format not in ALLOWED_FORMATS:
                raise ImageValidationError("Unsupported image type; use JPEG, PNG or WebP")
            width, height = img.size
            if width * height > limit:
                raise ImageValidationError(
                    f"Image is {width}x{height}; the limit is {limit:,} pixels"
                )
            img.load()
        except ImageValidationError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ImageValidationError(f"Image exceeds the {limit:,} pixel limit") from None
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            raise ImageValidationError("Not a valid JPEG, PNG or WebP image") from None
    return img


def image_mime_and_ext(img: Image.Image) -> tuple:
    """MIME type and canonical extension for an image returned by decode_image."""
    return ALLOWED_FORMATS[img.format]


def pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=95)
    return buf.getvalue()
