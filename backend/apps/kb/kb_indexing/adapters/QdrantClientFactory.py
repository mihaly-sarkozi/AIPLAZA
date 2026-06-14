from __future__ import annotations

from core.kernel.config.config_loader import settings


class QdrantConfigError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class QdrantClientFactory:
    def create_client(self):
        from qdrant_client import QdrantClient

        url = str(settings.qdrant_url or "").strip()
        if not url:
            raise QdrantConfigError("QDRANT_CONFIG_MISSING", "Missing qdrant_url")
        api_key = str(settings.qdrant_api_key or "").strip() or None
        timeout = int(settings.qdrant_timeout_sec or 120)
        return QdrantClient(
            url=url,
            api_key=api_key,
            timeout=timeout,
            check_compatibility=False,
        )


__all__ = ["QdrantClientFactory", "QdrantConfigError"]
