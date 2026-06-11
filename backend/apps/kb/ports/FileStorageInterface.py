from __future__ import annotations

from typing import Protocol


class FileStorageInterface(Protocol):
    """KB nyers anyag tárolása — egyetlen szerződés szöveghez és fájlhoz.

    Implementáció: ``infra.kb.MinioFileStorage`` (vagy más infra adapter).
    """

    def store_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str:
        """Szöveg mentése; visszaadja a raw_ref kulcsot."""
        ...

    def store_file(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> str:
        """Fájl mentése; visszaadja a raw_ref kulcsot."""
        ...

    def read_bytes(self, *, raw_ref: str) -> bytes:
        """Nyers anyag betöltése a raw_ref kulcs alapján (understanding pipeline)."""
        ...


__all__ = ["FileStorageInterface"]
