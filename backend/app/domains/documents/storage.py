"""Object storage abstraction (local filesystem for development, S3-compatible for deployed environments).

Keys never contain user-supplied filenames: ``tenants/{tenant}/documents/{document}/{version}``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings

_KEY_RE = re.compile(r"^[a-z0-9/-]+$")
CHUNK = 1024 * 1024


class ObjectStorage(Protocol):
    def put(self, key: str, stream: BinaryIO, content_type: str) -> None: ...
    def open(self, key: str) -> Iterator[bytes]: ...
    def exists(self, key: str) -> bool: ...


def _check_key(key: str) -> str:
    if not _KEY_RE.match(key) or ".." in key or key.startswith("/"):
        raise ValueError("Invalid storage key")
    return key


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / _check_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def put(self, key: str, stream: BinaryIO, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".partial")
        with open(tmp, "wb") as fh:
            while chunk := stream.read(CHUNK):
                fh.write(chunk)
        os.replace(tmp, path)

    def open(self, key: str) -> Iterator[bytes]:
        path = self._path(key)

        def _iter() -> Iterator[bytes]:
            with open(path, "rb") as fh:
                while chunk := fh.read(CHUNK):
                    yield chunk

        return _iter()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage:
    def __init__(self, bucket: str, endpoint_url: str | None, region: str) -> None:
        import boto3

        self.bucket = bucket
        # Credentials come from the standard AWS provider chain (IAM role in AWS, env vars locally).
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    def put(self, key: str, stream: BinaryIO, content_type: str) -> None:
        self.client.upload_fileobj(
            stream, self.bucket, _check_key(key),
            ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
        )

    def open(self, key: str) -> Iterator[bytes]:
        body = self.client.get_object(Bucket=self.bucket, Key=_check_key(key))["Body"]
        return iter(lambda: body.read(CHUNK), b"")

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_check_key(key))
            return True
        except Exception:
            return False


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        s = get_settings()
        if s.storage_backend == "s3":
            if not s.s3_bucket:
                raise RuntimeError("QS_S3_BUCKET is required when QS_STORAGE_BACKEND=s3")
            _storage = S3Storage(s.s3_bucket, s.s3_endpoint_url, s.s3_region)
        else:
            _storage = LocalStorage(s.storage_local_path)
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
