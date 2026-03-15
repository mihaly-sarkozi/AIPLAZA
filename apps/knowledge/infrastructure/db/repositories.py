from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, delete, or_, func
from config.settings import settings
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.infrastructure.db.models import KBORM, KbUserPermissionORM, KbTrainingLogORM, KbPersonalDataORM
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem
from apps.knowledge.pii.encryption import PiiEncryptor


class MySQLKnowledgeBaseRepository(KnowledgeBaseRepositoryPort):

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._pii_encryptor = PiiEncryptor()

    def _to_domain(self, orm: KBORM) -> KnowledgeBase:
        return KnowledgeBase(
            id=orm.id,
            uuid=orm.uuid,
            name=orm.name,
            description=orm.description,
            qdrant_collection_name=orm.qdrant_collection_name,
            personal_data_mode=getattr(orm, "personal_data_mode", None) or "no_personal_data",
            personal_data_sensitivity=getattr(orm, "personal_data_sensitivity", None) or "medium",
            created_at=orm.created_at,
            updated_at=orm.updated_at
        )

    def list_all(self):
        with self.session_factory() as session:
            stmt = select(KBORM)
            result = session.execute(stmt).scalars().all()
            return [self._to_domain(x) for x in result]

    def get_by_uuid(self, uuid: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    def get_by_id(self, kb_id: int):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.id == kb_id)
            orm = session.execute(stmt).scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    def get_by_name(self, name: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.name == name)
            orm = session.execute(stmt).scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    def create(self, kb: KnowledgeBase):
        with self.session_factory() as session:
            orm = KBORM(
                uuid=kb.uuid,
                name=kb.name,
                description=kb.description,
                qdrant_collection_name=kb.qdrant_collection_name,
                personal_data_mode=getattr(kb, "personal_data_mode", None) or "no_personal_data",
                personal_data_sensitivity=getattr(kb, "personal_data_sensitivity", None) or "medium",
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return self._to_domain(orm)

    def update(self, kb: KnowledgeBase):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == kb.uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            if not orm:
                return None

            orm.name = kb.name
            orm.description = kb.description
            if hasattr(orm, "personal_data_mode"):
                orm.personal_data_mode = getattr(kb, "personal_data_mode", None) or "no_personal_data"
            if hasattr(orm, "personal_data_sensitivity"):
                orm.personal_data_sensitivity = getattr(kb, "personal_data_sensitivity", None) or "medium"
            orm.updated_at = kb.updated_at

            session.commit()
            return self._to_domain(orm)

    def delete(self, uuid: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            if orm:
                session.delete(orm)
                session.commit()

    def list_permissions(self, kb_uuid: str) -> list[KbPermissionItem]:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                return []
            stmt = select(KbUserPermissionORM.user_id, KbUserPermissionORM.permission).where(
                KbUserPermissionORM.kb_id == kb.id
            )
            rows = session.execute(stmt).all()
            return [(r[0], r[1]) for r in rows]

    def list_permissions_batch(self, kb_uuids: list[str]) -> dict[str, list[KbPermissionItem]]:
        if not kb_uuids:
            return {}
        with self.session_factory() as session:
            kb_rows = session.execute(
                select(KBORM.id, KBORM.uuid).where(KBORM.uuid.in_(kb_uuids))
            ).all()
            id_to_uuid = {row[0]: row[1] for row in kb_rows}
            if not id_to_uuid:
                return {u: [] for u in kb_uuids}

            perm_rows = session.execute(
                select(KbUserPermissionORM.kb_id, KbUserPermissionORM.user_id, KbUserPermissionORM.permission).where(
                    KbUserPermissionORM.kb_id.in_(list(id_to_uuid.keys()))
                )
            ).all()
            out: dict[str, list[KbPermissionItem]] = {u: [] for u in kb_uuids}
            for kb_id, user_id, permission in perm_rows:
                kb_uuid = id_to_uuid.get(kb_id)
                if kb_uuid is None:
                    continue
                out[kb_uuid].append((user_id, permission))
            return out

    def add_training_log(
        self,
        kb_id: int,
        point_id: str,
        user_id: Optional[int],
        user_display: Optional[str],
        title: str,
        content: Optional[str],
        raw_content: Optional[str] = None,
        review_decision: Optional[str] = None,
    ) -> None:
        with self.session_factory() as session:
            session.add(
                KbTrainingLogORM(
                    kb_id=kb_id,
                    point_id=point_id,
                    user_id=user_id,
                    user_display=user_display or None,
                    title=title,
                    content=content,
                    raw_content=raw_content,
                    review_decision=review_decision,
                )
            )
            session.commit()

    def list_training_log(self, kb_uuid: str) -> list[dict]:
        return self.list_training_log_paginated(kb_uuid=kb_uuid, limit=50, offset=0, include_raw_content=False)

    def list_training_log_paginated(
        self,
        kb_uuid: str,
        limit: int = 50,
        offset: int = 0,
        include_raw_content: bool = False,
    ) -> list[dict]:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                return []
            stmt = (
                select(KbTrainingLogORM)
                .where(KbTrainingLogORM.kb_id == kb.id)
                .order_by(KbTrainingLogORM.created_at.desc())
                .limit(max(1, min(limit, 200)))
                .offset(max(0, offset))
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "point_id": r.point_id,
                    "user_id": r.user_id,
                    "user_display": r.user_display or "",
                    "title": r.title,
                    "content": r.content,
                    "raw_content": getattr(r, "raw_content", None) if include_raw_content else None,
                    "review_decision": getattr(r, "review_decision", None),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def delete_training_log_by_point_id(self, kb_id: int, point_id: str) -> bool:
        with self.session_factory() as session:
            session.execute(delete(KbPersonalDataORM).where(
                KbPersonalDataORM.kb_id == kb_id,
                KbPersonalDataORM.point_id == point_id,
            ))
            stmt = delete(KbTrainingLogORM).where(
                KbTrainingLogORM.kb_id == kb_id,
                KbTrainingLogORM.point_id == point_id,
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0

    def set_permissions(self, kb_uuid: str, permissions: list[KbPermissionItem]) -> None:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                raise ValueError("KB not found")
            session.execute(delete(KbUserPermissionORM).where(KbUserPermissionORM.kb_id == kb.id))
            for user_id, perm in permissions:
                if perm and perm != "none":
                    session.add(
                        KbUserPermissionORM(kb_id=kb.id, user_id=user_id, permission=perm)
                    )
            session.commit()

    def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]:
        """KB id-k ahol a user rendelkezik ezzel a jogosultsággal (train = use + train)."""
        with self.session_factory() as session:
            if permission == "use":
                stmt = select(KbUserPermissionORM.kb_id).where(
                    KbUserPermissionORM.user_id == user_id,
                    KbUserPermissionORM.permission.in_(["use", "train"]),
                )
            else:
                stmt = select(KbUserPermissionORM.kb_id).where(
                    KbUserPermissionORM.user_id == user_id,
                    KbUserPermissionORM.permission == permission,
                )
            rows = session.execute(stmt).scalars().all()
            return list(rows)

    def list_personal_data_by_point_id(self, kb_id: int, point_id: str) -> List[Tuple[str, str]]:
        """point_id-hez tartozó személyes adatok: [(reference_id, extracted_value), ...]."""
        with self.session_factory() as session:
            stmt = select(KbPersonalDataORM.reference_id, KbPersonalDataORM.extracted_value).where(
                KbPersonalDataORM.kb_id == kb_id,
                KbPersonalDataORM.point_id == point_id,
                or_(KbPersonalDataORM.expires_at.is_(None), KbPersonalDataORM.expires_at > datetime.utcnow()),
            )
            rows = session.execute(stmt).all()
            out: List[Tuple[str, str]] = []
            for ref_id, enc_value in rows:
                out.append((ref_id, self._pii_encryptor.decrypt(enc_value)))
            return out

    def add_personal_data(
        self, kb_id: int, point_id: str, data_type: str, extracted_value: str
    ) -> str:
        import uuid as uuid_mod
        ref_id = str(uuid_mod.uuid4())
        retention_days = int(getattr(settings, "pii_retention_days", 90) or 90)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=retention_days) if retention_days > 0 else None
        encrypted = self._pii_encryptor.encrypt(extracted_value)
        with self.session_factory() as session:
            session.add(
                KbPersonalDataORM(
                    kb_id=kb_id,
                    point_id=point_id,
                    data_type=data_type,
                    extracted_value=encrypted,
                    reference_id=ref_id,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
            session.commit()
        return ref_id

    def purge_expired_personal_data(self) -> int:
        with self.session_factory() as session:
            stmt = delete(KbPersonalDataORM).where(
                KbPersonalDataORM.expires_at.is_not(None),
                KbPersonalDataORM.expires_at <= datetime.utcnow(),
            )
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount or 0)

    def list_personal_data_records(self, kb_id: int, limit: int = 1000, offset: int = 0) -> List[dict]:
        with self.session_factory() as session:
            stmt = (
                select(
                    KbPersonalDataORM.reference_id,
                    KbPersonalDataORM.point_id,
                    KbPersonalDataORM.data_type,
                    KbPersonalDataORM.extracted_value,
                    KbPersonalDataORM.created_at,
                    KbPersonalDataORM.expires_at,
                )
                .where(KbPersonalDataORM.kb_id == kb_id)
                .order_by(KbPersonalDataORM.created_at.desc())
                .limit(max(1, min(limit, 20000)))
                .offset(max(0, offset))
            )
            rows = session.execute(stmt).all()
            out: List[dict] = []
            for ref_id, point_id, data_type, enc_value, created_at, expires_at in rows:
                out.append(
                    {
                        "reference_id": ref_id,
                        "point_id": point_id,
                        "data_type": data_type,
                        "value": self._pii_encryptor.decrypt(enc_value),
                        "created_at": created_at.isoformat() if created_at else None,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                    }
                )
            return out

    def delete_personal_data_by_reference_ids(self, kb_id: int, reference_ids: List[str]) -> int:
        if not reference_ids:
            return 0
        with self.session_factory() as session:
            stmt = delete(KbPersonalDataORM).where(
                KbPersonalDataORM.kb_id == kb_id,
                KbPersonalDataORM.reference_id.in_(reference_ids),
            )
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount or 0)

    def personal_data_metrics(self, kb_id: int) -> dict:
        now = datetime.utcnow()
        with self.session_factory() as session:
            total_stmt = select(func.count()).select_from(KbPersonalDataORM).where(
                KbPersonalDataORM.kb_id == kb_id,
                or_(KbPersonalDataORM.expires_at.is_(None), KbPersonalDataORM.expires_at > now),
            )
            expired_stmt = select(func.count()).select_from(KbPersonalDataORM).where(
                KbPersonalDataORM.kb_id == kb_id,
                KbPersonalDataORM.expires_at.is_not(None),
                KbPersonalDataORM.expires_at <= now,
            )
            by_type_stmt = (
                select(KbPersonalDataORM.data_type, func.count())
                .where(
                    KbPersonalDataORM.kb_id == kb_id,
                    or_(KbPersonalDataORM.expires_at.is_(None), KbPersonalDataORM.expires_at > now),
                )
                .group_by(KbPersonalDataORM.data_type)
                .order_by(func.count().desc())
            )
            total = int(session.execute(total_stmt).scalar() or 0)
            expired = int(session.execute(expired_stmt).scalar() or 0)
            by_type_rows = session.execute(by_type_stmt).all()
            by_type = [{"data_type": row[0], "count": int(row[1] or 0)} for row in by_type_rows]
            return {
                "total_active": total,
                "expired": expired,
                "by_type": by_type,
            }
