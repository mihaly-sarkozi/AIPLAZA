# apps/settings/domain/setting.py
# Rendszer beállítások domain modell
# 2026.03.07 - Sárközi Mihály

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Optional


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class Setting:
    id: Optional[int]
    key: str
    value: str
    updated_at: datetime
    updated_by: Optional[int]

    @classmethod
    def new(cls, key: str, value: str, updated_by: Optional[int] = None) -> "Setting":
        return cls(
            id=None,
            key=key,
            value=value,
            updated_at=_utcnow_naive(),
            updated_by=updated_by
        )

    def persisted(self, *, id: int, updated_at: datetime) -> "Setting":
        return replace(self, id=id, updated_at=updated_at)

    def with_value(self, value: str, updated_by: Optional[int] = None) -> "Setting":
        return replace(
            self,
            value=value,
            updated_at=_utcnow_naive(),
            updated_by=updated_by
        )
