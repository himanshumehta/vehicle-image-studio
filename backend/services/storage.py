"""Image storage.

Two interchangeable backends expose the same small interface used by the routers:

* ``LocalStorage`` (default) keeps images under ``LOCAL_STORAGE_DIR`` on disk and
  serves them through ``GET /api/files/{key}``.
* ``S3Storage`` talks to any S3-compatible bucket (AWS S3, MinIO, R2, Spaces...)
  when ``STORAGE_BACKEND=s3``. ``boto3`` is imported lazily, so it is only
  needed if you opt in.

Keys are POSIX-style relative paths such as ``vehicles/samples/hatchback.jpg``.
The first folder below ``vehicles/`` is treated as a collection in the gallery.
Every key that reaches a backend goes through :func:`validate_key`: relative,
no ``.``/``..`` segments, and an image extension, so the API can never read,
write or serve anything but image files inside the store.
"""
from __future__ import annotations

import mimetypes
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from config import REPO_ROOT, get_settings

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
COLLECTION_ROOT = "vehicles/"
MAX_KEY_LENGTH = 512


def derive_nobg_key(key: str) -> str:
    """``vehicles/a/b.jpg`` -> ``vehicles/a/b-nobg.png``."""
    base, _ = os.path.splitext(key)
    return f"{base}-nobg.png"


def _is_size_variant(key: str) -> bool:
    name = os.path.splitext(key.rsplit("/", 1)[-1])[0]
    return name.endswith("-medium") or name.endswith("-thumb")


def _is_nobg_variant(key: str) -> bool:
    name = os.path.splitext(key.rsplit("/", 1)[-1])[0]
    return name.endswith("-nobg")


class StorageError(Exception):
    pass


class InvalidKeyError(StorageError):
    """The key is malformed. The message is safe to show to clients."""


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
        raise InvalidKeyError("Invalid storage key")
    if key.startswith("/") or "\\" in key or "\x00" in key:
        raise InvalidKeyError("Invalid storage key")
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise InvalidKeyError("Invalid storage key")
    if not key.lower().endswith(IMAGE_EXTS):
        raise InvalidKeyError("Storage keys must end in .jpg, .jpeg, .png or .webp")
    return key


class LocalStorage:
    """Stores images as plain files below a root directory."""

    def __init__(self, root: str):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- helpers ------------------------------------------------------------
    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        # Defence in depth (symlinks): the resolved file must still be inside the root.
        if self.root not in path.parents:
            raise InvalidKeyError("Invalid storage key")
        return path

    def _record(self, path: Path) -> dict:
        stat = path.stat()
        key = path.relative_to(self.root).as_posix()
        return {
            "key": key,
            "size": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "url": self.generate_presigned_url(key),
        }

    def _all_image_paths(self, prefix: str = "") -> List[Path]:
        paths = [
            p for p in self.root.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]
        out = []
        for p in paths:
            key = p.relative_to(self.root).as_posix()
            if prefix and not key.startswith(prefix):
                continue
            try:
                validate_key(key)
            except InvalidKeyError:
                continue  # e.g. a hand-copied file with a backslash in its name
            out.append(p)
        return sorted(out, key=lambda p: p.relative_to(self.root).as_posix())

    # -- interface ----------------------------------------------------------
    # "token" here is a pagination cursor, not a credential.
    def list_images(self, prefix: str = "", max_keys: int = 50, continuation_token: str = "") -> dict:  # nosec B107
        start = int(continuation_token or 0)
        keys = [p.relative_to(self.root).as_posix() for p in self._all_image_paths(prefix)]
        nobg_keys = {k for k in keys if _is_nobg_variant(k)}
        originals = [k for k in keys if not _is_nobg_variant(k) and not _is_size_variant(k)]
        page = originals[start:start + max_keys]
        images = []
        for key in page:
            rec = self._record(self._path(key))
            nobg = derive_nobg_key(key)
            rec["has_nobg"] = nobg in nobg_keys
            rec["nobg_key"] = nobg if rec["has_nobg"] else None
            images.append(rec)
        next_token = str(start + max_keys) if start + max_keys < len(originals) else ""
        return {"images": images, "next_token": next_token}

    def list_brand_prefixes(self) -> List[dict]:
        base = self.root / COLLECTION_ROOT
        if not base.exists():
            return []
        groups = []
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            prefix = f"{COLLECTION_ROOT}{d.name}/"
            count = sum(
                1 for p in self._all_image_paths(prefix)
                if not _is_nobg_variant(p.name) and not _is_size_variant(p.name)
            )
            groups.append({
                "slug": d.name,
                "name": d.name.replace("-", " ").title(),
                "prefix": prefix,
                "image_count": count,
            })
        groups.sort(key=lambda g: g["image_count"], reverse=True)
        return groups

    def get_image_metadata(self, key: str) -> dict:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("Not found")
        rec = self._record(path)
        rec["content_type"] = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return rec

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        # Served by routers/images.py; the /api prefix lets the Next.js proxy reach it.
        return f"/api/files/{quote(key)}"

    def download_image(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("Not found")
        return path.read_bytes()

    def upload_image(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.generate_presigned_url(key)

    def delete_image(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def key_exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except StorageError:
            return False

    def local_path(self, key: str) -> Path:
        return self._path(key)

    def is_empty(self) -> bool:
        return not any(self._all_image_paths())


class S3Storage:
    """Any S3-compatible object store. Requires ``boto3`` (in requirements.txt)."""

    def __init__(self, bucket: str, region: str, endpoint_url: str, access_key: str, secret_key: str):
        import boto3
        from botocore.config import Config as BotoConfig

        if not bucket:
            raise StorageError("STORAGE_BACKEND=s3 requires S3_BUCKET")
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._groups_cache: Optional[List[dict]] = None
        self._groups_cache_ts: float = 0

    def _iter_objects(self, prefix: str):
        # S3 pagination cursor, not a credential.
        token = ""  # nosec B105
        while True:
            params: Dict = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                params["ContinuationToken"] = token
            resp = self.client.list_objects_v2(**params)
            for obj in resp.get("Contents", []):
                yield obj
            if not resp.get("IsTruncated"):
                return
            token = resp.get("NextContinuationToken", "")

    # "token" here is a pagination cursor, not a credential.
    def list_images(self, prefix: str = "", max_keys: int = 50, continuation_token: str = "") -> dict:  # nosec B107
        start = int(continuation_token or 0)
        objs = [o for o in self._iter_objects(prefix) if o["Key"].lower().endswith(IMAGE_EXTS)]
        nobg_keys = {o["Key"] for o in objs if _is_nobg_variant(o["Key"])}
        originals = [o for o in objs if not _is_nobg_variant(o["Key"]) and not _is_size_variant(o["Key"])]
        page = originals[start:start + max_keys]
        images = []
        for o in page:
            nobg = derive_nobg_key(o["Key"])
            images.append({
                "key": o["Key"],
                "size": o["Size"],
                "last_modified": o["LastModified"].isoformat(),
                "url": self.generate_presigned_url(o["Key"]),
                "has_nobg": nobg in nobg_keys,
                "nobg_key": nobg if nobg in nobg_keys else None,
            })
        next_token = str(start + max_keys) if start + max_keys < len(originals) else ""
        return {"images": images, "next_token": next_token}

    def list_brand_prefixes(self) -> List[dict]:
        now = time.time()
        if self._groups_cache is not None and now - self._groups_cache_ts < 60:
            return self._groups_cache
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=COLLECTION_ROOT, Delimiter="/")
        groups = []
        for cp in resp.get("CommonPrefixes", []):
            prefix = cp["Prefix"]
            slug = prefix.rstrip("/").split("/")[-1]
            count = sum(
                1 for o in self._iter_objects(prefix)
                if o["Key"].lower().endswith(IMAGE_EXTS)
                and not _is_nobg_variant(o["Key"]) and not _is_size_variant(o["Key"])
            )
            groups.append({"slug": slug, "name": slug.replace("-", " ").title(), "prefix": prefix, "image_count": count})
        groups.sort(key=lambda g: g["image_count"], reverse=True)
        self._groups_cache, self._groups_cache_ts = groups, now
        return groups

    def get_image_metadata(self, key: str) -> dict:
        head = self.client.head_object(Bucket=self.bucket, Key=validate_key(key))
        return {
            "key": key,
            "size": head["ContentLength"],
            "content_type": head["ContentType"],
            "last_modified": head["LastModified"].isoformat(),
            "url": self.generate_presigned_url(key),
        }

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )

    def download_image(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=validate_key(key))["Body"].read()

    def upload_image(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        self.client.put_object(Bucket=self.bucket, Key=validate_key(key), Body=data, ContentType=content_type)
        self._groups_cache = None
        return self.generate_presigned_url(key)

    def delete_image(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=validate_key(key))
        self._groups_cache = None

    def key_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=validate_key(key))
            return True
        except Exception:
            return False


def create_storage():
    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key,
        )
    if backend != "local":
        raise StorageError(f"Unknown STORAGE_BACKEND: {settings.storage_backend!r}")
    return LocalStorage(settings.local_storage_dir)


def seed_samples(storage) -> int:
    """Copy bundled sample images into an empty local store. Returns count copied."""
    if not isinstance(storage, LocalStorage) or not storage.is_empty():
        return 0
    samples_dir = Path(REPO_ROOT) / "samples"
    copied = 0
    for src in sorted(samples_dir.glob("*")):
        if src.suffix.lower() in IMAGE_EXTS:
            dest = storage.local_path(f"{COLLECTION_ROOT}samples/{src.name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            copied += 1
    return copied


storage = create_storage()
