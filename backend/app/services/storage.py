"""
Storage service — local filesystem or Cloudflare R2 (S3-compatible).

Switch via env var:
    STORAGE_BACKEND=local  (default)  → read/write under STORAGE_DIR
    STORAGE_BACKEND=r2                → read/write to R2 via boto3

Public API
----------
put_bytes(key, data, content_type)     upload raw bytes
put_file(key, local_path, content_type) upload from a local file (efficient multipart)
get_bytes(key)                         download and return bytes
exists(key)                            True if the object exists
public_url(key)                        URL the browser/client should use

Keys are the same relative paths used today, e.g.:
    books/<book_id>/pages/<page_id>/v001.png
    books/<book_id>/exports/MyBook_print_ready.pdf

For the local backend the key is resolved to STORAGE_DIR / key and the public
URL is /storage/<key> (the existing StaticFiles mount in main.py handles serving).

For the R2 backend the key is uploaded to the configured bucket and the public
URL is <R2_PUBLIC_BASE_URL>/<key>.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Union

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()
STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "storage"))

# R2 / S3 config (only needed when STORAGE_BACKEND=r2)
_R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
_R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
_R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
_R2_BUCKET: str = os.getenv("R2_BUCKET", "")
_R2_REGION: str = os.getenv("R2_REGION", "auto")
_R2_ENDPOINT: str = os.getenv(
    "R2_ENDPOINT",
    f"https://{_R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if _R2_ACCOUNT_ID else "",
)
_R2_PUBLIC_BASE_URL: str = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Lazy boto3 client (constructed once on first R2 use)
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3_client():
    """Return a cached boto3 S3 client configured for R2."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    import boto3
    _s3_client = boto3.client(
        "s3",
        endpoint_url=_R2_ENDPOINT,
        aws_access_key_id=_R2_ACCESS_KEY_ID,
        aws_secret_access_key=_R2_SECRET_ACCESS_KEY,
        region_name=_R2_REGION,
    )
    return _s3_client


# ---------------------------------------------------------------------------
# Local backend helpers
# ---------------------------------------------------------------------------

def _local_abs(key: str) -> Path:
    """Resolve a storage key to an absolute local path under STORAGE_DIR."""
    return STORAGE_DIR / key


def _local_put_bytes(key: str, data: bytes, content_type: str) -> None:
    dest = _local_abs(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _local_put_file(key: str, local_path: Union[str, Path], content_type: str) -> None:
    src = Path(local_path)
    dest = _local_abs(key)
    if src.resolve() == dest.resolve():
        # Source and destination are the same file — nothing to do.
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def _local_get_bytes(key: str) -> bytes:
    return _local_abs(key).read_bytes()


def _local_exists(key: str) -> bool:
    return _local_abs(key).exists()


def _local_delete(key: str) -> None:
    _local_abs(key).unlink(missing_ok=True)


def _local_public_url(key: str) -> str:
    # Normalise path separators to forward slash for URL safety.
    return "/storage/" + key.replace("\\", "/")


# ---------------------------------------------------------------------------
# R2 backend helpers
# ---------------------------------------------------------------------------

def _r2_put_bytes(key: str, data: bytes, content_type: str) -> None:
    import io
    _get_s3_client().put_object(
        Bucket=_R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def _r2_put_file(key: str, local_path: Union[str, Path], content_type: str) -> None:
    _get_s3_client().upload_file(
        Filename=str(local_path),
        Bucket=_R2_BUCKET,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def _r2_get_bytes(key: str) -> bytes:
    response = _get_s3_client().get_object(Bucket=_R2_BUCKET, Key=key)
    return response["Body"].read()


def _r2_exists(key: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        _get_s3_client().head_object(Bucket=_R2_BUCKET, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def _r2_delete(key: str) -> None:
    _get_s3_client().delete_object(Bucket=_R2_BUCKET, Key=key)


def _r2_public_url(key: str) -> str:
    if not _R2_PUBLIC_BASE_URL:
        raise RuntimeError(
            "R2_PUBLIC_BASE_URL is not set — cannot construct a public URL for R2 objects."
        )
    return _R2_PUBLIC_BASE_URL + "/" + key.replace("\\", "/")


# ---------------------------------------------------------------------------
# Public API — dispatch to whichever backend is active
# ---------------------------------------------------------------------------

def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload raw bytes to storage under the given key."""
    if STORAGE_BACKEND == "r2":
        _r2_put_bytes(key, data, content_type)
    else:
        _local_put_bytes(key, data, content_type)


def put_file(
    key: str,
    local_path: Union[str, Path],
    content_type: str = "application/octet-stream",
) -> None:
    """Upload a local file to storage under the given key."""
    if STORAGE_BACKEND == "r2":
        _r2_put_file(key, local_path, content_type)
    else:
        _local_put_file(key, local_path, content_type)


def get_bytes(key: str) -> bytes:
    """Download and return the raw bytes stored under the given key."""
    if STORAGE_BACKEND == "r2":
        return _r2_get_bytes(key)
    else:
        return _local_get_bytes(key)


def exists(key: str) -> bool:
    """Return True if the given key exists in storage."""
    if STORAGE_BACKEND == "r2":
        return _r2_exists(key)
    else:
        return _local_exists(key)


def delete_object(key: str) -> None:
    """Delete an object from storage. Idempotent (missing key is a no-op)."""
    if STORAGE_BACKEND == "r2":
        _r2_delete(key)
    else:
        _local_delete(key)


def public_url(key: str) -> str:
    """
    Return the public URL the browser should use to access the object.

    local → /storage/<key>         (served by the existing StaticFiles mount)
    r2    → <R2_PUBLIC_BASE_URL>/<key>
    """
    if STORAGE_BACKEND == "r2":
        return _r2_public_url(key)
    else:
        return _local_public_url(key)
