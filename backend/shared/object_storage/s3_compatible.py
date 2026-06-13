# backend/shared/object_storage/s3_compatible.py
# Feladat: S3-kompatibilis object storage adaptert valósít meg boto3 klienssel. Bucket létezést ellenőriz/létrehoz, byte/text feltöltést, letöltést, statot, törlést és normalizált object key építést biztosít az ObjectStoragePort contract szerint. Shared storage implementáció MinIO/S3-kompatibilis backendekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any, BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from shared.object_storage.config import ObjectStorageConfig
from shared.object_storage.contracts import ObjectStoragePort
from shared.object_storage.metadata import sanitize_s3_metadata
from shared.object_storage.models import StoredObjectData, StoredObjectRef

MAX_OBJECT_KEY_LENGTH = 1024


def sanitize_object_key_part(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or normalized in {".", ".."}:
        raise ValueError("Invalid object key segment")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise ValueError("Invalid control character in object key segment")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("Path separators are not allowed in object key segment")
    return normalized


class S3CompatibleObjectStorage(ObjectStoragePort):
    def __init__(self, config: ObjectStorageConfig) -> None:
        self._config = config
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            region_name=config.region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            use_ssl=config.secure,
            config=Config(s3={"addressing_style": "path" if config.force_path_style else "virtual"}),
        )

    def _resolve_bucket(self, bucket: str | None) -> str:
        resolved = (bucket or self._config.bucket or "").strip()
        if not resolved:
            raise ValueError("Object storage bucket is not configured")
        return resolved

    def _ensure_bucket_exists(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
            return
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code") or "")
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
        create_args: dict[str, Any] = {"Bucket": bucket}
        if (self._config.region or "") not in {"", "us-east-1"}:
            create_args["CreateBucketConfiguration"] = {"LocationConstraint": self._config.region}
        self._client.create_bucket(**create_args)

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        bucket: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef:
        resolved_bucket = self._resolve_bucket(bucket)
        self._ensure_bucket_exists(resolved_bucket)
        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = sanitize_s3_metadata(metadata)
        self._client.put_object(Bucket=resolved_bucket, Key=key, Body=content, **extra_args)
        head = self._client.head_object(Bucket=resolved_bucket, Key=key)
        return StoredObjectRef(
            provider=self._config.provider,
            bucket=resolved_bucket,
            key=key,
            etag=str(head.get("ETag") or "").strip('"') or None,
            size_bytes=int(head.get("ContentLength") or len(content)),
            content_type=head.get("ContentType"),
            metadata=dict(head.get("Metadata") or {}),
        )

    def put_fileobj(
        self,
        *,
        key: str,
        fileobj: BinaryIO,
        bucket: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef:
        resolved_bucket = self._resolve_bucket(bucket)
        self._ensure_bucket_exists(resolved_bucket)
        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = sanitize_s3_metadata(metadata)
        self._client.upload_fileobj(fileobj, resolved_bucket, key, ExtraArgs=extra_args or None)
        head = self._client.head_object(Bucket=resolved_bucket, Key=key)
        return StoredObjectRef(
            provider=self._config.provider,
            bucket=resolved_bucket,
            key=key,
            etag=str(head.get("ETag") or "").strip('"') or None,
            size_bytes=int(head.get("ContentLength") or 0),
            content_type=head.get("ContentType"),
            metadata=dict(head.get("Metadata") or {}),
        )

    def put_text(
        self,
        *,
        key: str,
        text: str,
        bucket: str | None = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef:
        return self.put_bytes(
            key=key,
            content=text.encode(encoding),
            bucket=bucket,
            content_type=content_type,
            metadata=metadata,
        )

    def get_bytes(self, *, key: str, bucket: str | None = None) -> StoredObjectData:
        resolved_bucket = self._resolve_bucket(bucket)
        result = self._client.get_object(Bucket=resolved_bucket, Key=key)
        body = result["Body"].read()
        return StoredObjectData(
            ref=StoredObjectRef(
                provider=self._config.provider,
                bucket=resolved_bucket,
                key=key,
                etag=str(result.get("ETag") or "").strip('"') or None,
                size_bytes=int(result.get("ContentLength") or len(body)),
                content_type=result.get("ContentType"),
                metadata=dict(result.get("Metadata") or {}),
            ),
            body=body,
        )

    def download_to_file(self, *, key: str, path: str, bucket: str | None = None) -> StoredObjectRef:
        resolved_bucket = self._resolve_bucket(bucket)
        result = self._client.get_object(Bucket=resolved_bucket, Key=key)
        try:
            with open(path, "wb") as handle:
                for chunk in iter(lambda: result["Body"].read(1024 * 1024), b""):
                    handle.write(chunk)
        finally:
            result["Body"].close()
        return self.stat_object(key=key, bucket=bucket)

    def stat_object(self, *, key: str, bucket: str | None = None) -> StoredObjectRef:
        resolved_bucket = self._resolve_bucket(bucket)
        head = self._client.head_object(Bucket=resolved_bucket, Key=key)
        return StoredObjectRef(
            provider=self._config.provider,
            bucket=resolved_bucket,
            key=key,
            etag=str(head.get("ETag") or "").strip('"') or None,
            size_bytes=int(head.get("ContentLength") or 0),
            content_type=head.get("ContentType"),
            metadata=dict(head.get("Metadata") or {}),
        )

    def delete_object(self, *, key: str, bucket: str | None = None) -> None:
        resolved_bucket = self._resolve_bucket(bucket)
        self._client.delete_object(Bucket=resolved_bucket, Key=key)

    def build_key(self, *parts: str) -> str:
        segments: list[str] = []
        for raw_part in parts:
            normalized_part = str(raw_part or "").strip().replace("\\", "/")
            split_segments = normalized_part.split("/")
            for segment in split_segments:
                segments.append(sanitize_object_key_part(segment))
        key = "/".join(segments)
        if len(key) > MAX_OBJECT_KEY_LENGTH:
            raise ValueError(f"Object key exceeds maximum length ({MAX_OBJECT_KEY_LENGTH})")
        return key


__all__ = ["MAX_OBJECT_KEY_LENGTH", "S3CompatibleObjectStorage", "sanitize_object_key_part"]
