# apps/settings/infrastructure/db/repositories/settings_repository.py
# Rendszer beállítások repository
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import SettingsORM
from apps.settings.ports import SettingsRepositoryInterface
from apps.settings.domain import Setting


class SettingsRepository(SettingsRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def get_by_key(self, key: str) -> Setting | None:
        with self._sf() as db:
            row = db.query(SettingsORM).filter(SettingsORM.key == key).first()
            if not row:
                return None
            return Setting(
                id=row.id,
                key=row.key,
                value=row.value,
                updated_at=self._normalize_dt(row.updated_at),
                updated_by=row.updated_by
            )

    def create_or_update(self, setting: Setting) -> Setting:
        with self._sf() as db:
            try:
                row = db.query(SettingsORM).filter(SettingsORM.key == setting.key).first()
                if row:
                    row.value = setting.value
                    row.updated_by = setting.updated_by
                    row.updated_at = setting.updated_at
                    db.commit()
                    db.refresh(row)
                    return Setting(
                        id=row.id,
                        key=row.key,
                        value=row.value,
                        updated_at=self._normalize_dt(row.updated_at),
                        updated_by=row.updated_by
                    )
                else:
                    row = SettingsORM(
                        key=setting.key,
                        value=setting.value,
                        updated_by=setting.updated_by
                    )
                    db.add(row)
                    db.commit()
                    db.refresh(row)
                    return setting.persisted(
                        id=row.id,
                        updated_at=self._normalize_dt(row.updated_at)
                    )
            except SQLAlchemyError:
                db.rollback()
                raise
