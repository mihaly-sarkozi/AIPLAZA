from __future__ import annotations

# backend/apps/kb/kb_crud/repository/KnowledgeBaseRepository.py
# Feladat: Tudástár perzisztencia (SQLAlchemy) — a kb_crud saját ORM modelljén.
# Sárközi Mihály - 2026.06.07

import uuid as uuid_lib

from sqlalchemy import delete, select

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.mapper.knowledge_base_mapper import kb_orm_to_domain
from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_crud.orm.KnowledgeBasePermissionORM import KnowledgeBasePermissionORM
from shared.utils.clock import utc_now_naive


class KnowledgeBaseRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        pii_depersonalization_enabled: bool,
        actor_user_id: int,
    ) -> KnowledgeBase:
        with self._session_factory() as session:
            kb_uuid = str(uuid_lib.uuid4())
            row = KnowledgeBaseORM(
                uuid=kb_uuid,
                name=name,
                description=description,
                qdrant_collection_name=f"kb_{kb_uuid}",
                pii_depersonalization_enabled=bool(pii_depersonalization_enabled),
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return kb_orm_to_domain(row)

    async def list_all(self, *, include_deleted: bool = False) -> list[KnowledgeBase]:
        with self._session_factory() as session:
            stmt = select(KnowledgeBaseORM)
            if not include_deleted:
                stmt = stmt.where(KnowledgeBaseORM.deleted_at.is_(None))
            rows = session.execute(
                stmt.order_by(KnowledgeBaseORM.created_at.desc(), KnowledgeBaseORM.id.desc())
            ).scalars().all()
            return [kb_orm_to_domain(row) for row in rows]

    async def get_by_uuid(self, kb_uuid: str) -> KnowledgeBase | None:
        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM).where(
                    KnowledgeBaseORM.uuid == kb_uuid,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            return kb_orm_to_domain(row) if row else None

    async def get_by_name(self, name: str) -> KnowledgeBase | None:
        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM).where(
                    KnowledgeBaseORM.name == name,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            return kb_orm_to_domain(row) if row else None

    async def update(
        self,
        kb_uuid: str,
        *,
        name: str,
        description: str | None,
        personal_data_mode: str | None,
        pii_depersonalization_enabled: bool | None,
        public_enabled: bool | None,
        actor_user_id: int,
    ) -> KnowledgeBase:
        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM).where(
                    KnowledgeBaseORM.uuid == kb_uuid,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if row is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

            row.name = name
            row.description = description
            if personal_data_mode:
                row.personal_data_mode = personal_data_mode
            if pii_depersonalization_enabled is not None:
                row.pii_depersonalization_enabled = bool(pii_depersonalization_enabled)
            if public_enabled is not None:
                row.public_enabled = bool(public_enabled)
            row.updated_by = actor_user_id
            session.commit()
            session.refresh(row)
            return kb_orm_to_domain(row)

    async def soft_delete(self, kb_uuid: str, *, training_char_count: int = 0) -> None:
        with self._session_factory() as session:
            row = session.execute(
                select(KnowledgeBaseORM).where(
                    KnowledgeBaseORM.uuid == kb_uuid,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if row is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

            session.execute(
                delete(KnowledgeBasePermissionORM).where(KnowledgeBasePermissionORM.kb_id == row.id)
            )
            row.deleted_display_name = row.name
            row.deleted_training_char_count = max(0, int(training_char_count or 0))
            row.deleted_at = utc_now_naive()
            row.updated_at = utc_now_naive()
            row.name = f"__deleted_{row.uuid[:10]}"
            session.commit()


__all__ = ["KnowledgeBaseRepository"]
