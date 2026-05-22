# backend/core/modules/brand/repository/brand_repository.py
# Feladat: Tenant brand beállítások adatbázis adaptere. Kiolvassa az első brand_settings sort, vagy update esetén létrehozza/frissíti a display név, logo URL, primary color, support email és public_enabled mezőket audit adatokkal. Brand repository réteg a BrandService számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func

from core.modules.brand.persistence.brand_settings_orm import BrandSettingsORM


class BrandRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    def get_settings(self) -> BrandSettingsORM | None:
        with self._sf() as db:
            return db.query(BrandSettingsORM).order_by(BrandSettingsORM.id.asc()).first()

    def upsert_settings(
        self,
        *,
        display_name: str,
        logo_url: str,
        primary_color: str,
        support_email: str,
        public_enabled: bool,
        updated_by: int | None = None,
    ) -> BrandSettingsORM:
        with self._sf() as db:
            try:
                row = db.query(BrandSettingsORM).order_by(BrandSettingsORM.id.asc()).first()
                if row is None:
                    row = BrandSettingsORM(
                        display_name=display_name,
                        logo_url=logo_url,
                        primary_color=primary_color,
                        support_email=support_email,
                        public_enabled=public_enabled,
                        created_by=updated_by,
                        updated_by=updated_by,
                    )
                    db.add(row)
                else:
                    row.display_name = display_name
                    row.logo_url = logo_url
                    row.primary_color = primary_color
                    row.support_email = support_email
                    row.public_enabled = public_enabled
                    row.updated_by = updated_by
                    row.updated_at = func.now()
                db.commit()
                db.refresh(row)
                return row
            except SQLAlchemyError:
                db.rollback()
                raise
