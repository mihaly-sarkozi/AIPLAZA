from __future__ import annotations

# backend/apps/kb/kb_crud/repository/KnowledgeBasePermissionRepository.py
# Feladat: Tudástár jogosultság perzisztencia (SQLAlchemy) — kb_user_permission tábla.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_crud.orm.KnowledgeBasePermissionORM import KnowledgeBasePermissionORM
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KbPermissionPair


class KnowledgeBasePermissionRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def list_permissions(self, kb_uuid: str) -> list[KbPermissionPair]:
        with self._session_factory() as session:
            kb_id = session.execute(
                select(KnowledgeBaseORM.id).where(
                    KnowledgeBaseORM.uuid == kb_uuid,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if kb_id is None:
                return []
            rows = session.execute(
                select(KnowledgeBasePermissionORM.user_id, KnowledgeBasePermissionORM.permission)
                .where(KnowledgeBasePermissionORM.kb_id == kb_id)
                .order_by(KnowledgeBasePermissionORM.user_id.asc())
            ).all()
            return [(user_id, permission) for user_id, permission in rows]

    async def list_permissions_batch(self, kb_uuids: list[str]) -> dict[str, list[KbPermissionPair]]:
        unique_uuids = list(dict.fromkeys(kb_uuids))
        if not unique_uuids:
            return {}
        with self._session_factory() as session:
            kb_rows = session.execute(
                select(KnowledgeBaseORM.id, KnowledgeBaseORM.uuid).where(
                    KnowledgeBaseORM.uuid.in_(unique_uuids),
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).all()
            result: dict[str, list[KbPermissionPair]] = {kb_uuid: [] for kb_uuid in unique_uuids}
            if not kb_rows:
                return result

            kb_id_to_uuid = {kb_id: kb_uuid for kb_id, kb_uuid in kb_rows}
            perm_rows = session.execute(
                select(
                    KnowledgeBasePermissionORM.kb_id,
                    KnowledgeBasePermissionORM.user_id,
                    KnowledgeBasePermissionORM.permission,
                ).where(KnowledgeBasePermissionORM.kb_id.in_(kb_id_to_uuid))
            ).all()
            for kb_id, user_id, permission in perm_rows:
                result[kb_id_to_uuid[kb_id]].append((user_id, permission))
            return result

    async def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[KbPermissionPair],
        *,
        actor_user_id: int,
    ) -> None:
        with self._session_factory() as session:
            kb_id = session.execute(
                select(KnowledgeBaseORM.id).where(
                    KnowledgeBaseORM.uuid == kb_uuid,
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if kb_id is None:
                raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

            session.execute(
                delete(KnowledgeBasePermissionORM).where(KnowledgeBasePermissionORM.kb_id == kb_id)
            )
            rows = [
                KnowledgeBasePermissionORM(
                    kb_id=kb_id,
                    user_id=user_id,
                    permission=permission,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                )
                for user_id, permission in permissions
                if permission in KbPermissionLevel.stored_values()
            ]
            if rows:
                session.add_all(rows)
            session.commit()

    async def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]:
        allowed = (
            {KbPermissionLevel.TRAIN.value}
            if permission == KbPermissionLevel.TRAIN.value
            else KbPermissionLevel.stored_values()
        )
        with self._session_factory() as session:
            rows = session.execute(
                select(KnowledgeBasePermissionORM.kb_id)
                .join(KnowledgeBaseORM, KnowledgeBaseORM.id == KnowledgeBasePermissionORM.kb_id)
                .where(
                    KnowledgeBasePermissionORM.user_id == user_id,
                    KnowledgeBasePermissionORM.permission.in_(allowed),
                    KnowledgeBaseORM.deleted_at.is_(None),
                )
                .distinct()
            ).all()
            return [kb_id for kb_id, in rows]


__all__ = ["KnowledgeBasePermissionRepository"]
