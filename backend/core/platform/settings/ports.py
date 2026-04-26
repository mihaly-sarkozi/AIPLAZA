from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SettingsRepositoryPort(Protocol):
    def get_by_key(self, key: str) -> str | None: ...

    def set_value(self, key: str, value: str, *, updated_by: int | None = None) -> None: ...


__all__ = ["SettingsRepositoryPort"]
