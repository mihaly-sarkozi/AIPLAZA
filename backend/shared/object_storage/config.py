from __future__ import annotations

from dataclasses import dataclass

from core.kernel.config import app_settings


@dataclass(frozen=True)
class ObjectStorageConfig:
    enabled: bool
    provider: str
    endpoint: str
    region: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    force_path_style: bool

    @property
    def endpoint_url(self) -> str:
        return (self.endpoint or "").strip()


def load_object_storage_config() -> ObjectStorageConfig:
    return ObjectStorageConfig(
        enabled=bool(getattr(app_settings, "object_storage_enabled", True)),
        provider=str(getattr(app_settings, "object_storage_provider", "s3_compatible") or "s3_compatible"),
        endpoint=str(getattr(app_settings, "object_storage_endpoint", "http://localhost:9000") or "http://localhost:9000"),
        region=str(getattr(app_settings, "object_storage_region", "us-east-1") or "us-east-1"),
        access_key=str(getattr(app_settings, "object_storage_access_key", "") or ""),
        secret_key=str(getattr(app_settings, "object_storage_secret_key", "") or ""),
        bucket=str(getattr(app_settings, "object_storage_bucket", "test-bucket-aiplaza") or "test-bucket-aiplaza"),
        secure=bool(getattr(app_settings, "object_storage_secure", False)),
        force_path_style=bool(getattr(app_settings, "object_storage_force_path_style", True)),
    )


__all__ = ["ObjectStorageConfig", "load_object_storage_config"]
