from __future__ import annotations

import os
import tempfile
from typing import BinaryIO, Protocol

from apps.kb.shared.errors import KbStorageError


class FileStorageInterface(Protocol):
    def store_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str: ...

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
    ) -> str: ...

    def read_bytes(self, *, raw_ref: str) -> bytes: ...

    def stat_bytes(self, *, raw_ref: str) -> int: ...

    def open_stream(self, *, raw_ref: str) -> BinaryIO: ...

    def materialize_to_temp_file(self, *, raw_ref: str) -> str: ...


__all__ = ["FileStorageInterface"]
