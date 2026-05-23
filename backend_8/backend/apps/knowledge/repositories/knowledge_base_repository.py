# Ez a fájl az adott terület adat-hozzáférési és perzisztencia logikáját tartalmazza.
from __future__ import annotations

from sqlalchemy import delete, select, text

from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.models import KBORM, KbUserPermissionORM
from apps.knowledge.models.utils import _utcnow_naive
from apps.knowledge.ports.repositories import KbPermissionItem


# Ez a függvény a(z) to_domain logikáját valósítja meg.
def _to_domain(row: KBORM) -> KnowledgeBase:
    display_name = row.name
    if row.deleted_at is not None:
        display_name = row.deleted_display_name or f"Törölt tudástár ({row.uuid[:8]})"
    return KnowledgeBase(
        id=row.id,
        uuid=row.uuid,
        name=display_name,
        description=row.description,
        qdrant_collection_name=row.qdrant_collection_name,
        personal_data_mode=row.personal_data_mode,
        personal_data_sensitivity=row.personal_data_sensitivity,
        pii_depersonalization_enabled=bool(getattr(row, "pii_depersonalization_enabled", True)),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        deleted_display_name=row.deleted_display_name,
        deleted_training_char_count=int(row.deleted_training_char_count or 0),
    )


class MySQLKnowledgeBaseRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory):
        self._sf = session_factory

    # Ez a metódus listázza a(z) all logikáját.
    def list_all(self, *, include_deleted: bool = False) -> list[KnowledgeBase]:
        with self._sf() as session:
            stmt = select(KBORM)
            if not include_deleted:
                stmt = stmt.where(KBORM.deleted_at.is_(None))
            rows = session.execute(
                stmt.order_by(KBORM.created_at.desc(), KBORM.id.desc())
            ).scalars().all()
            return [_to_domain(row) for row in rows]

    @staticmethod
    def _quote_identifier(value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    def database_size_bytes_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            schema = session.execute(text("select current_schema()")).scalar_one()
            table_rows = session.execute(
                text(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = :schema
                      and table_type = 'BASE TABLE'
                      and (table_name like 'knowledge_%' or table_name = 'kb_user_permission')
                    """
                ),
                {"schema": schema},
            ).all()
            total_bytes = 0.0
            kb_id = session.execute(select(KBORM.id).where(KBORM.uuid == corpus_uuid)).scalar_one_or_none()
            for (table_name,) in table_rows:
                columns = {
                    name
                    for (name,) in session.execute(
                        text(
                            """
                            select column_name
                            from information_schema.columns
                            where table_schema = :schema and table_name = :table_name
                            """
                        ),
                        {"schema": schema, "table_name": table_name},
                    ).all()
                }
                relation = f"{self._quote_identifier(str(schema))}.{self._quote_identifier(str(table_name))}"
                table_size = int(
                    session.execute(text(f"select pg_total_relation_size('{relation}'::regclass)")).scalar_one() or 0
                )
                if table_size <= 0:
                    continue
                total_rows = int(session.execute(text(f"select count(*) from {relation}")).scalar_one() or 0)
                if total_rows <= 0:
                    continue
                corpus_rows = 0
                if "corpus_uuid" in columns:
                    corpus_rows = int(
                        session.execute(
                            text(f"select count(*) from {relation} where corpus_uuid = :corpus_uuid"),
                            {"corpus_uuid": corpus_uuid},
                        ).scalar_one()
                        or 0
                    )
                elif table_name == "knowledge_bases" and "uuid" in columns:
                    corpus_rows = int(
                        session.execute(
                            text(f"select count(*) from {relation} where uuid = :corpus_uuid"),
                            {"corpus_uuid": corpus_uuid},
                        ).scalar_one()
                        or 0
                    )
                elif table_name == "kb_user_permission" and kb_id is not None and "kb_id" in columns:
                    corpus_rows = int(
                        session.execute(
                            text(f"select count(*) from {relation} where kb_id = :kb_id"),
                            {"kb_id": kb_id},
                        ).scalar_one()
                        or 0
                    )
                if corpus_rows > 0:
                    total_bytes += table_size * (corpus_rows / total_rows)
            return max(0, int(round(total_bytes)))

    # Ez a metódus visszaadja a(z) by uuid logikáját.
    def get_by_uuid(self, uuid: str) -> KnowledgeBase | None:
        with self._sf() as session:
            row = session.execute(select(KBORM).where(KBORM.uuid == uuid, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            return _to_domain(row) if row else None

    # Ez a metódus visszaadja a(z) by id logikáját.
    def get_by_id(self, kb_id: int) -> KnowledgeBase | None:
        with self._sf() as session:
            row = session.get(KBORM, kb_id)
            return _to_domain(row) if row and row.deleted_at is None else None

    # Ez a metódus visszaadja a(z) by name logikáját.
    def get_by_name(self, name: str) -> KnowledgeBase | None:
        with self._sf() as session:
            row = session.execute(select(KBORM).where(KBORM.name == name, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            return _to_domain(row) if row else None

    # Ez a metódus létrehozza a(z) create logikáját.
    def create(self, kb: KnowledgeBase, *, actor_user_id: int) -> KnowledgeBase:
        with self._sf() as session:
            row = KBORM(
                uuid=kb.uuid,
                name=kb.name,
                description=kb.description,
                qdrant_collection_name=kb.qdrant_collection_name,
                personal_data_mode=kb.personal_data_mode,
                personal_data_sensitivity=kb.personal_data_sensitivity,
                pii_depersonalization_enabled=bool(getattr(kb, "pii_depersonalization_enabled", True)),
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    # Ez a metódus frissíti a(z) update logikáját.
    def update(self, kb: KnowledgeBase, *, actor_user_id: int) -> KnowledgeBase:
        with self._sf() as session:
            row = session.execute(select(KBORM).where(KBORM.uuid == kb.uuid, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            if row is None:
                raise ValueError(f"Knowledge base not found: {kb.uuid}")
            row.name = kb.name
            row.description = kb.description
            row.personal_data_mode = kb.personal_data_mode
            row.personal_data_sensitivity = kb.personal_data_sensitivity
            row.pii_depersonalization_enabled = bool(getattr(kb, "pii_depersonalization_enabled", True))
            row.updated_by = actor_user_id
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    # Ez a metódus törli a(z) delete logikáját.
    def delete(self, uuid: str, *, training_char_count: int = 0) -> None:
        with self._sf() as session:
            kb_row = session.execute(select(KBORM).where(KBORM.uuid == uuid, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            if kb_row is None:
                return
            session.execute(delete(KbUserPermissionORM).where(KbUserPermissionORM.kb_id == kb_row.id))
            kb_row.deleted_display_name = kb_row.name
            kb_row.deleted_training_char_count = max(0, int(training_char_count or 0))
            kb_row.deleted_at = _utcnow_naive()
            kb_row.updated_at = _utcnow_naive()
            kb_row.name = f"__deleted_{kb_row.uuid[:10]}"
            session.commit()

    # Ez a metódus listázza a(z) permissions logikáját.
    def list_permissions(self, kb_uuid: str) -> list[KbPermissionItem]:
        with self._sf() as session:
            kb_id = session.execute(select(KBORM.id).where(KBORM.uuid == kb_uuid, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            if kb_id is None:
                return []
            rows = session.execute(
                select(KbUserPermissionORM.user_id, KbUserPermissionORM.permission)
                .where(KbUserPermissionORM.kb_id == kb_id)
                .order_by(KbUserPermissionORM.user_id.asc())
            ).all()
            return [(user_id, permission) for user_id, permission in rows]

    # Ez a metódus listázza a(z) permissions batch logikáját.
    def list_permissions_batch(self, kb_uuids: list[str]) -> dict[str, list[KbPermissionItem]]:
        unique_uuids = list(dict.fromkeys(kb_uuids))
        if not unique_uuids:
            return {}

        with self._sf() as session:
            kb_rows = session.execute(
                select(KBORM.id, KBORM.uuid).where(KBORM.uuid.in_(unique_uuids), KBORM.deleted_at.is_(None))
            ).all()
            if not kb_rows:
                return {kb_uuid: [] for kb_uuid in unique_uuids}

            kb_id_to_uuid = {kb_id: kb_uuid for kb_id, kb_uuid in kb_rows}
            result = {kb_uuid: [] for kb_uuid in unique_uuids}
            perm_rows = session.execute(
                select(
                    KbUserPermissionORM.kb_id,
                    KbUserPermissionORM.user_id,
                    KbUserPermissionORM.permission,
                ).where(KbUserPermissionORM.kb_id.in_(kb_id_to_uuid))
            ).all()

            for kb_id, user_id, permission in perm_rows:
                result[kb_id_to_uuid[kb_id]].append((user_id, permission))

            return result

    # Ez a metódus beállítja a(z) permissions logikáját.
    def set_permissions(self, kb_uuid: str, permissions: list[KbPermissionItem], *, actor_user_id: int) -> None:
        with self._sf() as session:
            kb_id = session.execute(select(KBORM.id).where(KBORM.uuid == kb_uuid, KBORM.deleted_at.is_(None))).scalar_one_or_none()
            if kb_id is None:
                raise ValueError(f"Knowledge base not found: {kb_uuid}")

            session.execute(delete(KbUserPermissionORM).where(KbUserPermissionORM.kb_id == kb_id))

            rows = [
                KbUserPermissionORM(
                    kb_id=kb_id,
                    user_id=user_id,
                    permission=permission,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                )
                for user_id, permission in permissions
                if permission in {"use", "train"}
            ]
            if rows:
                session.add_all(rows)
            session.commit()

    # Ez a metódus visszaadja a(z) KB ids with jogosultság logikáját.
    def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]:
        allowed_permissions = {"train"} if permission == "train" else {"use", "train"}
        with self._sf() as session:
            rows = session.execute(
                select(KbUserPermissionORM.kb_id)
                .join(KBORM, KBORM.id == KbUserPermissionORM.kb_id)
                .where(
                    KbUserPermissionORM.user_id == user_id,
                    KbUserPermissionORM.permission.in_(allowed_permissions),
                    KBORM.deleted_at.is_(None),
                )
                .distinct()
            ).all()
            return [kb_id for kb_id, in rows]
