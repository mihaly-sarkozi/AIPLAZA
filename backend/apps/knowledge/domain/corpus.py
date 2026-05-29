from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Corpus:
    id: int | None
    tenant: str
    uuid: str
    name: str
    description: str | None
    qdrant_collection_name: str
    created_at: datetime | None
    updated_at: datetime | None
    personal_data_mode: str = "no_personal_data"
    personal_data_sensitivity: str = "medium"
    pii_depersonalization_enabled: bool = True
    public_enabled: bool = False
    deleted_at: datetime | None = None
    deleted_display_name: str | None = None
    deleted_training_char_count: int = 0

    @property
    def is_public(self) -> bool:
        return self.public_enabled


__all__ = ["Corpus"]
