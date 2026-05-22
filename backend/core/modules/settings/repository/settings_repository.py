# backend/core/modules/settings/repository/settings_repository.py
# Feladat: A perzisztált settings kulcs-érték adatok repository adaptere. Tenant DB session factoryval olvas és upsertel SettingsORM rekordokat, commit/rollback kezeléssel SQLAlchemy hibák esetén. Settings adat-hozzáférési réteg a SettingsService alatt.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from core.modules.settings.models.settings_orm import SettingsORM


class SettingsRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    def get_by_key(self, key: str) -> str | None:
        with self._sf() as db:
            row = db.query(SettingsORM).filter(SettingsORM.key == key).first()
            if row is None:
                return None
            return row.value

    def set_value(self, key: str, value: str, *, updated_by: int | None = None) -> None:
        from sqlalchemy import func

        with self._sf() as db:
            try:
                row = db.query(SettingsORM).filter(SettingsORM.key == key).first()
                if row is not None:
                    row.value = value
                    row.updated_by = updated_by
                    row.updated_at = func.now()
                    db.commit()
                    return

                row = SettingsORM(
                    key=key,
                    value=value,
                    created_by=updated_by,
                    updated_by=updated_by,
                )
                db.add(row)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise


__all__ = ["SettingsRepository"]
