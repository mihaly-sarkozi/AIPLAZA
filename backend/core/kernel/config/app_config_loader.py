from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.dev import DevAppConfig
from core.kernel.config.environment import get_app_env, load_project_env

class EnvAppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    app_name: str
    app_description: str
    app_version: str

    openai_api_key: str
    qdrant_url: str
    qdrant_api_key: str = ""
    qdrant_timeout_sec: int
    object_storage_enabled: bool = True
    object_storage_provider: str = "s3_compatible"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_region: str = "us-east-1"
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_bucket: str = "test-bucket-aiplaza"
    object_storage_secure: bool = False
    object_storage_force_path_style: bool = True

    pii_encryption_key: str
    pii_retention_days: int

    @model_validator(mode="after")
    def validate_production_settings(self):
        env = get_app_env()
        if env == "prod":
            if not (self.pii_encryption_key or "").strip():
                raise ValueError("pii_encryption_key kötelező production környezetben.")
            if int(self.pii_retention_days) <= 0:
                raise ValueError("pii_retention_days productionben 0-nál nagyobb kell legyen.")
            if self.object_storage_enabled:
                if not (self.object_storage_access_key or "").strip():
                    raise ValueError("object_storage_access_key kötelező production környezetben.")
                if not (self.object_storage_secret_key or "").strip():
                    raise ValueError("object_storage_secret_key kötelező production környezetben.")
                if not (self.object_storage_bucket or "").strip():
                    raise ValueError("object_storage_bucket kötelező production környezetben.")
        return self


@lru_cache(maxsize=1)
def get_app_settings():
    load_project_env()
    env = get_app_env()
    if env == "prod":
        return EnvAppConfig()
    return DevAppConfig()

def load_app_config():
    return get_app_settings()


def __getattr__(name: str):
    if name == "app_settings":
        return get_app_settings()
    raise AttributeError(name)


__all__ = ["app_settings", "get_app_settings", "load_app_config"]
