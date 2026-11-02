"""Application settings, read from environment variables or a `.env` file.

Every variable is optional: with no configuration at all the studio runs fully
offline with local-disk storage and permissively licensed models.
See `.env.example` at the repository root for the full list.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BACKEND_DIR)

# Largest accepted image upload (bytes), for every endpoint that takes one.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class Settings(BaseSettings):
    # --- Storage -----------------------------------------------------------
    # "local" (default) stores images on disk; "s3" uses any S3-compatible bucket.
    storage_backend: str = "local"
    local_storage_dir: str = os.path.join(REPO_ROOT, "data", "storage")
    seed_samples: bool = True  # copy samples/ into an empty local store on startup

    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""  # empty = AWS default endpoint
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # --- Models ------------------------------------------------------------
    # Background removal backend:
    #   u2net (default) | isnet-general-use | birefnet-general ... -> rembg (ONNX, no torch at runtime)
    #   birefnet  -> ZhengPeng7/BiRefNet via transformers (needs requirements-models.txt)
    #   rmbg-2.0  -> briaai/RMBG-2.0 via transformers (NON-COMMERCIAL licence, gated, needs HF_TOKEN)
    bg_removal_model: str = "u2net"
    hf_token: str = ""
    models_dir: str = os.path.join(BACKEND_DIR, "models")

    # --- Optional image-edit (inpainting) providers ---------------------------
    image_edit_provider: str = "openai"  # "openai" or "gemini"
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"

    # --- HTTP --------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"

    model_config = {
        "env_file": (os.path.join(REPO_ROOT, ".env"), os.path.join(BACKEND_DIR, ".env")),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        # Relative paths in .env are relative to the repository root, not the CWD.
        for field in ("local_storage_dir", "models_dir"):
            value = os.path.expanduser(getattr(self, field))
            if not os.path.isabs(value):
                value = os.path.normpath(os.path.join(REPO_ROOT, value))
            setattr(self, field, value)
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
