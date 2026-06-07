from __future__ import annotations

import uuid as uuid_lib

from sqlalchemy import delete, select

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.mapper.knowledge_base_mapper import kb_orm_to_domain
from apps.knowledge.models import KBORM, KbUserPermissionORM
from shared.utils.clock import utc_now_naive


class KnowledgeBaseRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        actor_user_id: int,
    ) -> KnowledgeBase:
        with self._session_factory() as session:
            existing = session.execute(
                select(KBORM).where(KBORM.name == name, KBORM.deleted_at.is_(None))
            ).scalar_one_or_none()
            if existing is not None:
                raise CrudValidationError(CrudErrorCode.KB_NAME_EXISTS)

            kb_uuid = str(uuid_lib.uuid4())
            row = KBORM(
                uuid=kb_uuid,
                name=name,
                description=description,
                qdrant_collection_name=f"kb_{kb_uuid}",
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            session.add(row)
            session.flush()
            session.add(
                KbUserPermissionORM(
                    kb_id=row.id,
                    user_id=actor_user_id,
                    permission="train",
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                )
            )
            session.commit()
            session.refresh(row)
            return kb_orm_to_domain(row)

    async def list_all(self) -> list[KnowledgeBase]:
        with self._session_factory() as session:
            rows = session.execute(
                select(KBORM)
                .where(KBORM.deleted_at.is_(None))
                .order_by(KBORM.created_at.desc(), KBORM.id.desc())
            ).scalars().all()
            return [kb_orm_to_domain(row) for row in rows]

    async def get_by_id(self, kb_id: str) -> KnowledgeBase:
        with self._session_factory() as session:
            row = session.execute(
                select(KBORM).where(KBORM.uuid == kb_id, KBORM.deleted_at.is_(None))
            ).scalar_one_or_none()
            if row is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)
            return kb_orm_to_domain(row)

    async def update(
        self,
        kb_id: str,
        *,
        name: str,
        description: str | None,
        actor_user_id: int,
    ) -> KnowledgeBase:
        with self._session_factory() as session:
            row = session.execute(
                select(KBORM).where(KBORM.uuid == kb_id, KBORM.deleted_at.is_(None))
            ).scalar_one_or_none()
            if row is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

            duplicate = session.execute(
                select(KBORM).where(
                    KBORM.name == name,
                    KBORM.deleted_at.is_(None),
                    KBORM.uuid != kb_id,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                raise CrudValidationError(CrudErrorCode.KB_NAME_EXISTS)

            row.name = name
            row.description = description
            row.updated_by = actor_user_id
            session.commit()
            session.refresh(row)
            return kb_orm_to_domain(row)

    async def archive(self, kb_id: str) -> None:
        with self._session_factory() as session:
            row = session.execute(
                select(KBORM).where(KBORM.uuid == kb_id, KBORM.deleted_at.is_(None))
            ).scalar_one_or_none()
            if row is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

            session.execute(delete(KbUserPermissionORM).where(KbUserPermissionORM.kb_id == row.id))
            row.deleted_display_name = row.name
            row.deleted_at = utc_now_naive()
            row.updated_at = utc_now_naive()
            row.name = f"__deleted_{row.uuid[:10]}"
            session.commit()


__all__ = ["KnowledgeBaseRepository"]
