"""Gallery endpoints: list, inspect, import, save and delete images in storage."""
from __future__ import annotations

import logging
import mimetypes
import os
import re

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from routers.uploads import read_upload
from services.storage import InvalidKeyError, LocalStorage, StorageError, derive_nobg_key, storage
from utils.image_helpers import ImageValidationError, decode_image, image_mime_and_ext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])
files_router = APIRouter(prefix="/api/files", tags=["files"])

MAX_PAGE_SIZE = 200
_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")
_MAX_SEGMENT_LENGTH = 100


def _slug(text: str) -> str:
    slug = _SAFE_SEGMENT.sub("-", text.strip()).strip("-.").lower()[:_MAX_SEGMENT_LENGTH]
    return slug or "untitled"


def _storage_failure(action: str) -> HTTPException:
    logger.exception("Storage %s failed", action)
    return HTTPException(500, f"Storage {action} failed; see the server log")


def _validated_image(data: bytes) -> tuple:
    """(content type, canonical extension) of an uploaded image, or a 400."""
    try:
        return image_mime_and_ext(decode_image(data))
    except ImageValidationError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_images(
    prefix: str = Query("", max_length=512),
    max_keys: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    continuation_token: str = Query("", pattern=r"^\d*$", max_length=12),
):
    try:
        result = storage.list_images(prefix=prefix, max_keys=max_keys, continuation_token=continuation_token)
    except Exception:
        raise _storage_failure("listing")
    return {"images": result["images"], "count": len(result["images"]), "next_token": result["next_token"]}


@router.get("/brands")
async def list_collections():
    """Folders directly below ``vehicles/`` (kept as ``brands`` for API compatibility)."""
    try:
        groups = storage.list_brand_prefixes()
    except Exception:
        raise _storage_failure("listing")
    return {
        "brands": groups,
        "total_brands": len(groups),
        "total_images": sum(g["image_count"] for g in groups),
    }


@router.post("/import")
async def import_image(file: UploadFile = File(...), collection: str = Form("uploads", max_length=200)):
    """Add a new image to the gallery under ``vehicles/<collection>/``.

    The extension and content type come from the decoded image, not from the
    client's filename or header.
    """
    data = await read_upload(file)
    content_type, ext = _validated_image(data)
    name = os.path.splitext(file.filename or "image")[0]
    key = f"vehicles/{_slug(collection)}/{_slug(name)}{ext}"
    try:
        url = storage.upload_image(key, data, content_type)
    except Exception:
        raise _storage_failure("write")
    return {"key": key, "url": url, "size": len(data)}


@router.post("/upload")
async def save_image(key: str = Form(...), file: UploadFile = File(...)):
    """Save an edited image back to storage at ``key`` (overwrites)."""
    data = await read_upload(file)
    content_type, _ = _validated_image(data)
    try:
        url = storage.upload_image(key, data, content_type)
    except InvalidKeyError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise _storage_failure("write")
    return {"key": key, "url": url, "size": len(data)}


@router.get("/detail/{key:path}")
async def get_image(key: str):
    try:
        metadata = storage.get_image_metadata(key)
    except InvalidKeyError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(404, "Image not found")
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
    except InvalidKeyError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise _storage_failure("delete")
    return {"deleted": key}


@files_router.get("/{key:path}")
async def serve_file(key: str):
    """Serve a stored image (local backend) or proxy it from the bucket (S3 backend)."""
    media_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    if isinstance(storage, LocalStorage):
        try:
            path = storage.local_path(key)
        except StorageError:
            raise HTTPException(404, "Not found")
        if not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(path, media_type=media_type)
    try:
        data = storage.download_image(key)
    except Exception:
        raise HTTPException(404, "Not found")
    return Response(content=data, media_type=media_type)
