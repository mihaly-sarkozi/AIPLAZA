from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BrandRepositoryPort(Protocol):
    def get_settings(self): ...

    def upsert_settings(
        self,
        *,
        display_name: str,
        logo_url: str,
        primary_color: str,
        support_email: str,
        public_enabled: bool,
        updated_by: int | None = None,
    ): ...


__all__ = ["BrandRepositoryPort"]
