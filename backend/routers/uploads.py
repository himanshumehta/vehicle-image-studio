"""Reading multipart uploads with a hard size cap."""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

from config import MAX_UPLOAD_BYTES


async def read_upload(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read at most ``limit`` bytes; anything longer is a 413, never fully buffered."""
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Image too large; the limit is {limit // (1024 * 1024)} MB")
    return data
