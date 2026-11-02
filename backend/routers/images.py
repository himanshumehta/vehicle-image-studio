"""Gallery endpoints: list, inspect, import, save and delete images in storage."""
from __future__ import annotations

import logging
import mimetypes
import os
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from config import MAX_UPLOAD_BYTES
from services.storage import LocalStorage, StorageError, derive_nobg_key, storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])
files_router = APIRouter(prefix="/api/files", tags=["files"])

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug(text: str) -> str:
    return _SAFE_SEGMENT.sub("-", text.strip()).strip("-.").lower() or "untitled"


@router.get("")
async def list_images(prefix: str = "", max_keys: int = 50, continuation_token: str = ""):
    try:
        result = storage.list_images(prefix=prefix, max_keys=max_keys, continuation_token=continuation_token)
        return {"images": result["images"], "count": len(result["images"]), "next_token": result["next_token"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brands")
async def list_collections():
    """Folders directly below ``vehicles/`` (kept as ``brands`` for API compatibility)."""
    try:
        groups = storage.list_brand_prefixes()
        return {
            "brands": groups,
            "total_brands": len(groups),
            "total_images": sum(g["image_count"] for g in groups),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_image(file: UploadFile = File(...), collection: str = Form("uploads")):
    """Add a new image to the gallery under ``vehicles/<collection>/``."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image too large. Max 25 MB.")
    name, ext = os.path.splitext(file.filename or "image.png")
    ext = ext.lower() if ext.lower() in (".jpg", ".jpeg", ".png", ".webp") else ".png"
    key = f"vehicles/{_slug(collection)}/{_slug(name)}{ext}"
    content_type = file.content_type or mimetypes.guess_type(key)[0] or "image/png"
    url = storage.upload_image(key, data, content_type)
    return {"key": key, "url": url, "size": len(data)}


@router.post("/upload")
async def save_image(key: str = Form(...), file: UploadFile = File(...)):
    """Save an edited image back to storage at ``key`` (overwrites)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image too large. Max 25 MB.")
    try:
        url = storage.upload_image(key, data, file.content_type or "image/png")
    except StorageError as e:
        raise HTTPException(400, str(e))
    return {"key": key, "url": url, "size": len(data)}


@router.get("/detail/{key:path}")
async def get_image(key: str):
    try:
        metadata = storage.get_image_metadata(key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Image not found: {e}")
    nobg_key = derive_nobg_key(key)
    exists = storage.key_exists(nobg_key)
    metadata["nobg_variant"] = {
        "key": nobg_key,
        "exists": exists,
        "url": storage.generate_presigned_url(nobg_key) if exists else None,
    }
    return metadata


@router.delete("/detail/{key:path}")
async def delete_image(key: str):
    try:
        storage.delete_image(key)
        return {"deleted": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@files_router.get("/{key:path}")
async def serve_file(key: str):
    """Serve a stored file (local backend) or redirect-free proxy (S3 backend)."""
    if isinstance(storage, LocalStorage):
        try:
            path = storage.local_path(key)
        except StorageError:
            raise HTTPException(404, "Not found")
        if not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(path)
    try:
        data = storage.download_image(key)
    except Exception:
        raise HTTPException(404, "Not found")
    return Response(content=data, media_type=mimetypes.guess_type(key)[0] or "application/octet-stream")
