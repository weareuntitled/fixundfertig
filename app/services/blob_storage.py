from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


_KEY_PATTERN = re.compile(r"^companies/\d+/documents/\d{4}/\d{2}/[^/]+/[^/]+$")


class BlobStorage(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes, mime: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    return cleaned or "document"


def _safe_filename(name: str) -> str:
    cleaned = (name or "").strip() or "document"
    cleaned = os.path.basename(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß _\.\(\)\[\]\-]+", "_", cleaned)
    cleaned = cleaned.replace("/", "_").replace("\\", "_").replace(":", "_")
    return cleaned[:120] if len(cleaned) > 120 else cleaned


def _validate_key(key: str) -> None:
    if key.startswith("/") or key.startswith("../") or "/../" in key:
        raise ValueError("Ungültiger Storage-Key.")
    if not _KEY_PATTERN.match(key):
        raise ValueError("Ungültige Key-Struktur.")


def build_document_key(
    company_id: int | str,
    document_id: int | str,
    filename: str,
    *,
    now: datetime | None = None,
) -> str:
    timestamp = now or datetime.now()
    year = timestamp.strftime("%Y")
    month = timestamp.strftime("%m")
    safe_doc_id = _safe_segment(str(document_id))
    safe_name = _safe_filename(filename)
    key = f"companies/{company_id}/documents/{year}/{month}/{safe_doc_id}/{safe_name}"
    _validate_key(key)
    return key


class LocalStorage(BlobStorage):
    def __init__(self, root: str) -> None:
        self._root = root

    def _full_path(self, key: str) -> Path:
        _validate_key(key)
        root = Path(self._root).resolve()
        path = (root / key).resolve()
        if not str(path).startswith(str(root)):
            raise ValueError("Ungültiger Storage-Key.")
        return path

    def put_bytes(self, key: str, data: bytes, mime: str) -> None:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        path = self._full_path(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._full_path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        path = self._full_path(key)
        return path.exists()


class S3Storage(BlobStorage):
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
    ) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
        )

    @classmethod
    def from_env(cls) -> "S3Storage":
        bucket = os.getenv("S3_BUCKET", "").strip()
        region = os.getenv("S3_REGION", "").strip()
        access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
        secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
        endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
        if not bucket or not region or not access_key_id or not secret_access_key:
            raise ValueError("S3 Konfiguration unvollständig.")
        return cls(
            bucket=bucket,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
        )

    def put_bytes(self, key: str, data: bytes, mime: str) -> None:
        _validate_key(key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=mime or "application/octet-stream",
        )

    def get_bytes(self, key: str) -> bytes:
        _validate_key(key)
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        body = obj.get("Body")
        return body.read() if body is not None else b""

    def delete(self, key: str) -> None:
        _validate_key(key)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        _validate_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


_STORAGE_INSTANCE: BlobStorage | None = None


def blob_storage() -> BlobStorage:
    global _STORAGE_INSTANCE
    if _STORAGE_INSTANCE is not None:
        return _STORAGE_INSTANCE
    backend = (os.getenv("STORAGE_BACKEND", "local") or "local").strip().lower()
    if backend == "s3":
        _STORAGE_INSTANCE = S3Storage.from_env()
    else:
        root = (os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage").strip()
        _STORAGE_INSTANCE = LocalStorage(root=root)
    return _STORAGE_INSTANCE
