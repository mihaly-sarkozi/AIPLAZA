from __future__ import annotations

# backend/apps/kb/kb_training/storage/TrainingStorage.py
# Feladat: Tanítási nyers anyag tároló port (outbound) — a composition root ObjectStoragePort-ot injektál.
# Sárközi Mihály - 2026.06.07

from typing import Protocol


class TrainingStorage(Protocol):
    """Nyers tanítási tartalom perzisztálása előre felépített storage kulccsal."""

    def put_text(
        self,
        *,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> None: ...


__all__ = ["TrainingStorage"]
