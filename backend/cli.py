#!/usr/bin/env python3
"""Command-line access to the same services the API uses (no server needed).

    python cli.py remove-bg  ../samples/hatchback.jpg  ../out/hatchback-nobg.png
    python cli.py upscale    ../samples/hatchback.jpg  ../out/hatchback-4x.png --scale 4
    python cli.py clean      ../samples/hatchback.jpg  ../out/hatchback-clean.png --preset remove_plate_and_watermark

``clean`` needs OPENAI_API_KEY or GEMINI_API_KEY; the other commands run offline.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def cmd_remove_bg(args) -> None:
    from services.background_removal import bg_removal_service

    with open(args.input, "rb") as f:
        data = f.read()
    t0 = time.perf_counter()
    out = bg_removal_service.remove_background(data)
    _write(args.output, out)
    print(f"{args.output}  ({bg_removal_service.model_name}, {time.perf_counter() - t0:.1f}s)")


def cmd_upscale(args) -> None:
    from PIL import Image

    from services.upscale_service import upscale_service
    from utils.image_helpers import pil_to_bytes

    img = Image.open(args.input)
    t0 = time.perf_counter()
    out = upscale_service.upscale(img, scale=args.scale)
    _write(args.output, pil_to_bytes(out, fmt="PNG"))
    print(f"{args.output}  {img.width}x{img.height} -> {out.width}x{out.height} ({time.perf_counter() - t0:.1f}s)")


def cmd_clean(args) -> None:
    from image_edit_providers import create_image_edit_provider
    from image_edit_providers.base import CLEANUP_PRESETS

    editor = create_image_edit_provider(args.provider)
    if editor is None:
        sys.exit("No image-edit provider configured: set OPENAI_API_KEY or GEMINI_API_KEY (see .env.example)")
    prompt = args.prompt or CLEANUP_PRESETS[args.preset]["prompt"]
    with open(args.input, "rb") as f:
        data = f.read()
    t0 = time.perf_counter()
    result = asyncio.run(editor.edit_image(image_bytes=data, prompt=prompt, quality=args.quality))
    _write(args.output, result.image_bytes)
    print(f"{args.output}  ({result.provider}/{result.model}, {time.perf_counter() - t0:.1f}s)")


def main() -> None:
    from image_edit_providers.base import CLEANUP_PRESETS

    parser = argparse.ArgumentParser(description="Vehicle Image Studio CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("remove-bg", help="cut out the vehicle (transparent PNG)")
    p.add_argument("input")
    p.add_argument("output")
    p.set_defaults(func=cmd_remove_bg)

    p = sub.add_parser("upscale", help="Real-ESRGAN super-resolution")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--scale", type=int, choices=[2, 4, 8], default=4)
    p.set_defaults(func=cmd_upscale)

    p = sub.add_parser("clean", help="remove number plate / watermark with an image-edit model")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--preset", choices=sorted(CLEANUP_PRESETS), default="remove_plate_and_watermark")
    p.add_argument("--prompt", help="free-form instruction instead of a preset")
    p.add_argument("--provider", choices=["openai", "gemini"])
    p.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    p.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
