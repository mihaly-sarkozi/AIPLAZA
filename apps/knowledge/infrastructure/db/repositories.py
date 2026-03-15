from datetime import UTC, datetime, timedelta
from math import exp
from typing import List, Optional, Tuple
from sqlalchemy import select, delete, or_, func, and_
from config.settings import settings
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.infrastructure.db.models import (
    KBORM,
    KbUserPermissionORM,
    KbTrainingLogORM,
    KbPersonalDataORM,
    KbSentenceORM,
    KbMentionORM,
    KbEntityORM,
    KbEntityAliasORM,
    KbPlaceORM,
    KbAssertionORM,
    KbStructuralChunkORM,
    KbAssertionEvidenceORM,
    KbAssertionRelationORM,
    KbReinforcementEventORM,
    KbTimeIntervalORM,
    KbVectorOutboxORM,
)
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem
from apps.knowledge.pii.encryption import PiiEncryptor
from apps.knowledge.application.scoring import compute_relation_confidence


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában (DB kompatibilis)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_entity_key(name: str, entity_type: str) -> str:
    return f"{(entity_type or 'UNKNOWN').strip().lower()}::{(name or '').strip().lower()}"


def _current_relation_weight(weight: float, relation_type: str, created_at: datetime | None) -> float:
    if created_at is None:
        return float(weight)
    decay_by_type = {
        "SAME_SUBJECT": 0.003,
        "SAME_OBJECT": 0.004,
        "SAME_PREDICATE": 0.006,
        "SAME_PLACE": 0.008,
        "SAME_SOURCE_POINT": 0.01,
        "TEMPORALLY_OVERLAPS": 0.006,
    }
    lam = float(decay_by_type.get(str(relation_type or "").upper(), 0.007))
    delta_days = max(0.0, (_utcnow_naive() - created_at).total_seconds() / 86400.0)
    baseline = max(0.05, float(weight) * 0.25)
    decayed = baseline + (float(weight) - baseline) * exp(-lam * delta_days)
    return max(baseline, min(float(weight), decayed))


class MySQLKnowledgeBaseRepository(KnowledgeBaseRepositoryPort):

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._pii_encryptor = PiiEncryptor()

    def _estimate_token_count(self, text: str) -> int:
        """Egyszerű token becslés MVP-hez (szó alapú)."""
        cleaned = (text or "").strip()
        if not cleaned:
            return 0
        return len([p for p in cleaned.split() if p])

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
        idempotency_key: Optional[str] = None,
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
                    idempotency_key=idempotency_key,
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

    def get_training_log_by_idempotency_key(self, kb_id: int, idempotency_key: str) -> Optional[dict]:
        key = (idempotency_key or "").strip()
        if not key:
            return None
        with self.session_factory() as session:
            row = session.execute(
                select(KbTrainingLogORM).where(
                    KbTrainingLogORM.kb_id == kb_id,
                    KbTrainingLogORM.idempotency_key == key,
                )
            ).scalar_one_or_none()
            if not row:
                return None
            return {
                "point_id": row.point_id,
                "title": row.title,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

    def get_training_log_entry(self, kb_id: int, point_id: str) -> Optional[dict]:
        with self.session_factory() as session:
            row = session.execute(
                select(KbTrainingLogORM).where(
                    KbTrainingLogORM.kb_id == kb_id,
                    KbTrainingLogORM.point_id == point_id,
                )
            ).scalar_one_or_none()
            if not row:
                return None
            return {
                "point_id": row.point_id,
                "title": row.title,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

    def enqueue_vector_outbox(
        self,
        kb_id: int,
        operation_type: str,
        payload: dict,
        source_point_id: Optional[str] = None,
    ) -> int:
        with self.session_factory() as session:
            row = KbVectorOutboxORM(
                kb_id=kb_id,
                source_point_id=source_point_id,
                operation_type=operation_type,
                payload=payload or {},
                status="pending",
                attempts=0,
                next_retry_at=_utcnow_naive(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)

    def list_due_vector_outbox(self, limit: int = 50) -> List[dict]:
        with self.session_factory() as session:
            now = _utcnow_naive()
            rows = session.execute(
                select(KbVectorOutboxORM)
                .where(
                    KbVectorOutboxORM.status.in_(["pending", "failed"]),
                    KbVectorOutboxORM.next_retry_at <= now,
                )
                .order_by(KbVectorOutboxORM.next_retry_at.asc(), KbVectorOutboxORM.id.asc())
                .limit(max(1, min(limit, 500)))
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "kb_id": r.kb_id,
                    "source_point_id": r.source_point_id,
                    "operation_type": r.operation_type,
                    "payload": r.payload or {},
                    "status": r.status,
                    "attempts": r.attempts or 0,
                    "next_retry_at": r.next_retry_at,
                }
                for r in rows
            ]

    def mark_vector_outbox_done(self, outbox_id: int) -> None:
        with self.session_factory() as session:
            row = session.execute(
                select(KbVectorOutboxORM).where(KbVectorOutboxORM.id == outbox_id)
            ).scalar_one_or_none()
            if not row:
                return
            row.status = "done"
            row.processed_at = _utcnow_naive()
            row.updated_at = _utcnow_naive()
            session.commit()

    def mark_vector_outbox_retry(self, outbox_id: int, error: str, backoff_seconds: int) -> None:
        with self.session_factory() as session:
            row = session.execute(
                select(KbVectorOutboxORM).where(KbVectorOutboxORM.id == outbox_id)
            ).scalar_one_or_none()
            if not row:
                return
            row.status = "failed"
            row.attempts = int((row.attempts or 0) + 1)
            row.last_error = (error or "")[:2000]
            row.next_retry_at = _utcnow_naive() + timedelta(seconds=max(5, backoff_seconds))
            row.updated_at = _utcnow_naive()
            session.commit()

    def get_vector_outbox_stats(self, kb_id: Optional[int] = None, recent_limit: int = 20) -> dict:
        now = _utcnow_naive()
        with self.session_factory() as session:
            base_conditions = []
            if kb_id is not None:
                base_conditions.append(KbVectorOutboxORM.kb_id == kb_id)

            total_stmt = select(func.count()).select_from(KbVectorOutboxORM)
            if base_conditions:
                total_stmt = total_stmt.where(and_(*base_conditions))
            total = int(session.execute(total_stmt).scalar() or 0)

            by_status_stmt = (
                select(KbVectorOutboxORM.status, func.count())
                .group_by(KbVectorOutboxORM.status)
            )
            if base_conditions:
                by_status_stmt = by_status_stmt.where(and_(*base_conditions))
            by_status_rows = session.execute(by_status_stmt).all()
            by_status = {str(row[0]): int(row[1] or 0) for row in by_status_rows}

            by_operation_stmt = (
                select(KbVectorOutboxORM.operation_type, func.count())
                .group_by(KbVectorOutboxORM.operation_type)
            )
            if base_conditions:
                by_operation_stmt = by_operation_stmt.where(and_(*base_conditions))
            by_operation_rows = session.execute(by_operation_stmt).all()
            by_operation = {str(row[0]): int(row[1] or 0) for row in by_operation_rows}

            oldest_due_stmt = select(func.min(KbVectorOutboxORM.next_retry_at)).where(
                KbVectorOutboxORM.status.in_(["pending", "failed"]),
                KbVectorOutboxORM.next_retry_at <= now,
            )
            if base_conditions:
                oldest_due_stmt = oldest_due_stmt.where(and_(*base_conditions))
            oldest_due = session.execute(oldest_due_stmt).scalar()

            max_attempts_stmt = select(func.max(KbVectorOutboxORM.attempts))
            if base_conditions:
                max_attempts_stmt = max_attempts_stmt.where(and_(*base_conditions))
            max_attempts = int(session.execute(max_attempts_stmt).scalar() or 0)

            recent_stmt = (
                select(KbVectorOutboxORM)
                .order_by(KbVectorOutboxORM.updated_at.desc(), KbVectorOutboxORM.id.desc())
                .limit(max(1, min(recent_limit, 100)))
            )
            if base_conditions:
                recent_stmt = recent_stmt.where(and_(*base_conditions))
            recent_rows = session.execute(recent_stmt).scalars().all()
            recent_items = [
                {
                    "id": int(row.id),
                    "kb_id": int(row.kb_id),
                    "source_point_id": row.source_point_id,
                    "operation_type": row.operation_type,
                    "status": row.status,
                    "attempts": int(row.attempts or 0),
                    "last_error": row.last_error,
                    "next_retry_at": row.next_retry_at.isoformat() if row.next_retry_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "processed_at": row.processed_at.isoformat() if row.processed_at else None,
                }
                for row in recent_rows
            ]

            return {
                "total": total,
                "by_status": by_status,
                "by_operation": by_operation,
                "max_attempts": max_attempts,
                "oldest_due_at": oldest_due.isoformat() if oldest_due else None,
                "recent_items": recent_items,
            }

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
                or_(KbPersonalDataORM.expires_at.is_(None), KbPersonalDataORM.expires_at > _utcnow_naive()),
            )
            rows = session.execute(stmt).all()
            out: List[Tuple[str, str]] = []
            for ref_id, enc_value in rows:
                out.append((ref_id, self._pii_encryptor.decrypt(enc_value)))
            return out

    def add_personal_data(
        self, kb_id: int, point_id: str, data_type: str, extracted_value: str
    ) -> str:
        retention_days = int(getattr(settings, "pii_retention_days", 90) or 90)
        now = _utcnow_naive()
        expires_at = now + timedelta(days=retention_days) if retention_days > 0 else None
        encrypted = self._pii_encryptor.encrypt(extracted_value)
        with self.session_factory() as session:
            row = KbPersonalDataORM(
                kb_id=kb_id,
                point_id=point_id,
                data_type=data_type,
                extracted_value=encrypted,
                # Flush után a tényleges integer PK-ból képezzük a reference_id-t.
                reference_id="0",
                created_at=now,
                expires_at=expires_at,
            )
            session.add(row)
            session.flush()
            row.reference_id = str(row.id)
            session.commit()
        return str(row.reference_id)

    def purge_expired_personal_data(self) -> int:
        with self.session_factory() as session:
            stmt = delete(KbPersonalDataORM).where(
                KbPersonalDataORM.expires_at.is_not(None),
                KbPersonalDataORM.expires_at <= _utcnow_naive(),
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
        now = _utcnow_naive()
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

    def create_sentence_batch(self, kb_id: int, source_point_id: str, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        with self.session_factory() as session:
            inserted: List[KbSentenceORM] = []
            for idx, row in enumerate(rows):
                text_value = (row.get("text") or "").strip()
                sanitized = (row.get("sanitized_text") or text_value).strip()
                orm = KbSentenceORM(
                    kb_id=kb_id,
                    source_point_id=source_point_id,
                    sentence_order=int(row.get("sentence_order", idx)),
                    text=text_value,
                    sanitized_text=sanitized,
                    token_count=int(row.get("token_count") or self._estimate_token_count(sanitized)),
                    entity_ids=row.get("entity_ids") or [],
                    assertion_ids=row.get("assertion_ids") or [],
                    predicate_hints=row.get("predicate_hints") or [],
                    time_from=row.get("time_from"),
                    time_to=row.get("time_to"),
                    place_keys=row.get("place_keys") or [],
                    qdrant_point_id=row.get("qdrant_point_id"),
                )
                session.add(orm)
                inserted.append(orm)
            session.commit()
            for row in inserted:
                session.refresh(row)
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "sentence_order": row.sentence_order,
                    "text": row.text,
                    "sanitized_text": row.sanitized_text,
                    "token_count": row.token_count,
                    "entity_ids": row.entity_ids or [],
                    "assertion_ids": row.assertion_ids or [],
                    "predicate_hints": row.predicate_hints or [],
                    "time_from": row.time_from,
                    "time_to": row.time_to,
                    "place_keys": row.place_keys or [],
                    "qdrant_point_id": row.qdrant_point_id,
                }
                for row in inserted
            ]

    def create_structural_chunk_batch(self, kb_id: int, source_point_id: str, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        with self.session_factory() as session:
            inserted: List[KbStructuralChunkORM] = []
            for idx, row in enumerate(rows):
                text_value = (row.get("text") or "").strip()
                sentence_ids = row.get("sentence_ids") or []
                orm = KbStructuralChunkORM(
                    kb_id=kb_id,
                    source_point_id=source_point_id,
                    chunk_order=int(row.get("chunk_order", idx)),
                    text=text_value,
                    sentence_ids=sentence_ids,
                    assertion_ids=row.get("assertion_ids") or [],
                    entity_ids=row.get("entity_ids") or [],
                    predicate_hints=row.get("predicate_hints") or [],
                    token_count=int(row.get("token_count") or self._estimate_token_count(text_value)),
                    time_from=row.get("time_from"),
                    time_to=row.get("time_to"),
                    place_keys=row.get("place_keys") or [],
                    qdrant_point_id=row.get("qdrant_point_id"),
                )
                session.add(orm)
                inserted.append(orm)
            session.commit()
            for row in inserted:
                session.refresh(row)
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "chunk_order": row.chunk_order,
                    "text": row.text,
                    "sentence_ids": row.sentence_ids or [],
                    "assertion_ids": row.assertion_ids or [],
                    "entity_ids": row.entity_ids or [],
                    "predicate_hints": row.predicate_hints or [],
                    "token_count": row.token_count,
                    "time_from": row.time_from,
                    "time_to": row.time_to,
                    "place_keys": row.place_keys or [],
                    "qdrant_point_id": row.qdrant_point_id,
                }
                for row in inserted
            ]

    def update_sentence_enrichment_batch(self, kb_id: int, rows: List[dict]) -> int:
        if not rows:
            return 0
        updated = 0
        with self.session_factory() as session:
            for row in rows:
                sentence_id = row.get("id")
                if sentence_id is None:
                    continue
                entity = session.execute(
                    select(KbSentenceORM).where(
                        KbSentenceORM.kb_id == kb_id,
                        KbSentenceORM.id == int(sentence_id),
                    )
                ).scalar_one_or_none()
                if entity is None:
                    continue
                entity.entity_ids = row.get("entity_ids") or []
                entity.assertion_ids = row.get("assertion_ids") or []
                entity.predicate_hints = row.get("predicate_hints") or []
                entity.time_from = row.get("time_from")
                entity.time_to = row.get("time_to")
                entity.place_keys = row.get("place_keys") or []
                updated += 1
            session.commit()
        return updated

    def update_structural_chunk_enrichment_batch(self, kb_id: int, rows: List[dict]) -> int:
        if not rows:
            return 0
        updated = 0
        with self.session_factory() as session:
            for row in rows:
                chunk_id = row.get("id")
                if chunk_id is None:
                    continue
                entity = session.execute(
                    select(KbStructuralChunkORM).where(
                        KbStructuralChunkORM.kb_id == kb_id,
                        KbStructuralChunkORM.id == int(chunk_id),
                    )
                ).scalar_one_or_none()
                if entity is None:
                    continue
                entity.assertion_ids = row.get("assertion_ids") or []
                entity.entity_ids = row.get("entity_ids") or []
                entity.predicate_hints = row.get("predicate_hints") or []
                entity.time_from = row.get("time_from")
                entity.time_to = row.get("time_to")
                entity.place_keys = row.get("place_keys") or []
                updated += 1
            session.commit()
        return updated

    def create_mentions_batch(self, sentence_id: int, rows: List[dict]) -> List[dict]:
        if not rows:
            return []
        with self.session_factory() as session:
            inserted: List[KbMentionORM] = []
            for row in rows:
                orm = KbMentionORM(
                    sentence_id=sentence_id,
                    surface_form=(row.get("surface_form") or "").strip(),
                    mention_type=(row.get("mention_type") or "UNKNOWN").strip(),
                    grammatical_role=row.get("grammatical_role"),
                    sentence_local_index=row.get("sentence_local_index"),
                    char_start=row.get("char_start"),
                    char_end=row.get("char_end"),
                    resolved_entity_id=row.get("resolved_entity_id"),
                    resolution_confidence=float(row.get("resolution_confidence") or 0.0),
                    is_implicit_subject=1 if bool(row.get("is_implicit_subject")) else 0,
                )
                session.add(orm)
                inserted.append(orm)
            session.commit()
            for row in inserted:
                session.refresh(row)
            return [
                {
                    "id": row.id,
                    "sentence_id": row.sentence_id,
                    "surface_form": row.surface_form,
                    "mention_type": row.mention_type,
                    "grammatical_role": row.grammatical_role,
                    "sentence_local_index": row.sentence_local_index,
                    "char_start": row.char_start,
                    "char_end": row.char_end,
                    "resolved_entity_id": row.resolved_entity_id,
                    "resolution_confidence": row.resolution_confidence or 0.0,
                    "is_implicit_subject": bool(row.is_implicit_subject),
                }
                for row in inserted
            ]

    def upsert_entity(self, kb_id: int, payload: dict) -> dict:
        canonical_name = (payload.get("canonical_name") or "").strip()
        entity_type = (payload.get("entity_type") or "UNKNOWN").strip()
        aliases = [str(x).strip() for x in (payload.get("aliases") or []) if str(x).strip()]
        now = _utcnow_naive()
        canonical_key = _normalize_entity_key(canonical_name, entity_type)
        with self.session_factory() as session:
            normalized_canonical = canonical_name.lower()
            alias_norms = sorted(set(x.lower() for x in aliases))

            row = session.execute(
                select(KbEntityORM).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.canonical_name == canonical_name,
                    KbEntityORM.entity_type == entity_type,
                )
            ).scalar_one_or_none()

            if row is None and alias_norms:
                alias_entity_id = session.execute(
                    select(KbEntityAliasORM.entity_id)
                    .join(KbEntityORM, KbEntityORM.id == KbEntityAliasORM.entity_id)
                    .where(
                        KbEntityORM.kb_id == kb_id,
                        KbEntityORM.entity_type == entity_type,
                        func.lower(KbEntityAliasORM.alias).in_(alias_norms + [normalized_canonical]),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if alias_entity_id is not None:
                    row = session.execute(select(KbEntityORM).where(KbEntityORM.id == alias_entity_id)).scalar_one_or_none()

            if row is None:
                row = session.execute(
                    select(KbEntityORM).where(
                        KbEntityORM.kb_id == kb_id,
                        KbEntityORM.canonical_key == canonical_key,
                    )
                ).scalar_one_or_none()

            if row is None:
                row = session.execute(
                    select(KbEntityORM).where(
                        KbEntityORM.kb_id == kb_id,
                        KbEntityORM.entity_type == entity_type,
                        func.lower(KbEntityORM.canonical_name) == normalized_canonical,
                    )
                ).scalar_one_or_none()

            if row:
                row.aliases = sorted(set((row.aliases or []) + list(aliases)))
                row.canonical_key = _normalize_entity_key(row.canonical_name or canonical_name, row.entity_type or entity_type)
                row.confidence = float(payload.get("confidence", row.confidence or 0.0))
                row.last_seen_at = now
            else:
                row = KbEntityORM(
                    kb_id=kb_id,
                    source_point_id=payload.get("source_point_id"),
                    canonical_name=canonical_name,
                    canonical_key=canonical_key,
                    entity_type=entity_type,
                    aliases=list(aliases),
                    confidence=float(payload.get("confidence") or 0.0),
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(row)
                session.flush()

            existing_aliases = {
                a[0]
                for a in session.execute(
                    select(KbEntityAliasORM.alias).where(KbEntityAliasORM.entity_id == row.id)
                ).all()
            }
            for alias in sorted(set(list(aliases) + [canonical_name])):
                if alias and alias not in existing_aliases:
                    session.add(KbEntityAliasORM(entity_id=row.id, alias=alias, alias_text=alias))
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "kb_id": row.kb_id,
                "source_point_id": row.source_point_id,
                "canonical_name": row.canonical_name,
                "canonical_key": row.canonical_key,
                "entity_type": row.entity_type,
                "aliases": row.aliases or [],
                "confidence": row.confidence or 0.0,
            }

    def get_entities_by_ids(self, kb_id: int, entity_ids: List[int]) -> List[dict]:
        if not entity_ids:
            return []
        with self.session_factory() as session:
            rows = session.execute(
                select(KbEntityORM).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.id.in_(entity_ids),
                )
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "canonical_name": row.canonical_name,
                    "canonical_key": row.canonical_key,
                    "entity_type": row.entity_type,
                    "aliases": row.aliases or [],
                    "confidence": row.confidence or 0.0,
                }
                for row in rows
            ]

    def merge_entities(self, kb_id: int, source_entity_id: int, target_entity_id: int) -> bool:
        if source_entity_id == target_entity_id:
            return False
        with self.session_factory() as session:
            source = session.execute(
                select(KbEntityORM).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.id == source_entity_id,
                )
            ).scalar_one_or_none()
            target = session.execute(
                select(KbEntityORM).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.id == target_entity_id,
                )
            ).scalar_one_or_none()
            if source is None or target is None:
                return False

            merged_aliases = sorted(set((target.aliases or []) + (source.aliases or []) + [source.canonical_name]))
            target.aliases = merged_aliases
            target.canonical_key = _normalize_entity_key(target.canonical_name, target.entity_type)

            session.execute(delete(KbEntityAliasORM).where(KbEntityAliasORM.entity_id == source_entity_id))
            existing_aliases = {
                a[0]
                for a in session.execute(
                    select(KbEntityAliasORM.alias).where(KbEntityAliasORM.entity_id == target_entity_id)
                ).all()
            }
            for alias in merged_aliases:
                if alias and alias not in existing_aliases:
                    session.add(KbEntityAliasORM(entity_id=target_entity_id, alias=alias, alias_text=alias))

            for a in session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    or_(
                        KbAssertionORM.subject_entity_id == source_entity_id,
                        KbAssertionORM.object_entity_id == source_entity_id,
                    ),
                )
            ).scalars().all():
                if a.subject_entity_id == source_entity_id:
                    a.subject_entity_id = target_entity_id
                if a.object_entity_id == source_entity_id:
                    a.object_entity_id = target_entity_id

            for m in session.execute(
                select(KbMentionORM).where(KbMentionORM.resolved_entity_id == source_entity_id)
            ).scalars().all():
                m.resolved_entity_id = target_entity_id

            session.execute(delete(KbEntityORM).where(KbEntityORM.id == source_entity_id))
            session.commit()
            return True

    def upsert_time_interval(self, kb_id: int, payload: dict) -> dict:
        normalized_text = (payload.get("normalized_text") or "").strip()
        valid_from = payload.get("valid_from")
        valid_to = payload.get("valid_to")
        granularity = (payload.get("granularity") or "unknown").strip()
        with self.session_factory() as session:
            row = session.execute(
                select(KbTimeIntervalORM).where(
                    KbTimeIntervalORM.kb_id == kb_id,
                    KbTimeIntervalORM.normalized_text == normalized_text,
                    KbTimeIntervalORM.valid_from == valid_from,
                    KbTimeIntervalORM.valid_to == valid_to,
                )
            ).scalar_one_or_none()
            if row:
                row.confidence = float(payload.get("confidence", row.confidence or 0.0))
            else:
                row = KbTimeIntervalORM(
                    kb_id=kb_id,
                    source_point_id=payload.get("source_point_id") or "",
                    normalized_text=normalized_text,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    granularity=granularity,
                    confidence=float(payload.get("confidence") or 0.0),
                )
                session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "kb_id": row.kb_id,
                "source_point_id": row.source_point_id,
                "normalized_text": row.normalized_text,
                "valid_from": row.valid_from,
                "valid_to": row.valid_to,
                "granularity": row.granularity,
                "confidence": row.confidence or 0.0,
            }

    def upsert_place(self, kb_id: int, payload: dict) -> dict:
        normalized_key = (payload.get("normalized_key") or "").strip().lower()
        canonical_name = (payload.get("canonical_name") or normalized_key).strip()
        with self.session_factory() as session:
            row = session.execute(
                select(KbPlaceORM).where(
                    KbPlaceORM.kb_id == kb_id,
                    KbPlaceORM.normalized_key == normalized_key,
                )
            ).scalar_one_or_none()
            if row:
                row.canonical_name = canonical_name or row.canonical_name
                row.place_type = payload.get("place_type", row.place_type)
                row.country_code = payload.get("country_code", row.country_code)
                row.parent_place_id = payload.get("parent_place_id", row.parent_place_id)
                row.confidence = float(payload.get("confidence", row.confidence or 0.0))
            else:
                row = KbPlaceORM(
                    kb_id=kb_id,
                    canonical_name=canonical_name,
                    normalized_key=normalized_key,
                    place_type=payload.get("place_type"),
                    country_code=payload.get("country_code"),
                    parent_place_id=payload.get("parent_place_id"),
                    confidence=float(payload.get("confidence") or 0.0),
                )
                session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "kb_id": row.kb_id,
                "canonical_name": row.canonical_name,
                "normalized_key": row.normalized_key,
                "place_type": row.place_type,
                "country_code": row.country_code,
                "parent_place_id": row.parent_place_id,
                "confidence": row.confidence,
            }

    def upsert_assertion(self, kb_id: int, payload: dict) -> dict:
        now = _utcnow_naive()
        fingerprint = (payload.get("assertion_fingerprint") or "").strip()
        created = False
        with self.session_factory() as session:
            stmt = select(KbAssertionORM).where(
                KbAssertionORM.kb_id == kb_id,
                KbAssertionORM.assertion_fingerprint == fingerprint,
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row:
                incoming_source_point = str(payload.get("source_point_id") or "").strip()
                row.evidence_count = int((row.evidence_count or 0) + int(payload.get("evidence_increment") or 1))
                row.reinforcement_count = int((row.reinforcement_count or 0) + int(payload.get("reinforcement_increment") or 1))
                row.last_reinforced_at = now
                row.confidence = float(payload.get("confidence", row.confidence or 0.0))
                row.strength = float(payload.get("strength", row.strength or 0.05))
                row.object_value = payload.get("object_value", row.object_value)
                row.assertion_primary_subject_mention_id = payload.get(
                    "assertion_primary_subject_mention_id",
                    row.assertion_primary_subject_mention_id,
                )
                row.subject_resolution_type = payload.get("subject_resolution_type", row.subject_resolution_type or "explicit")
                row.time_interval_id = payload.get("time_interval_id", row.time_interval_id)
                row.place_id = payload.get("place_id", row.place_id)
                row.time_from = payload.get("time_from", row.time_from)
                row.time_to = payload.get("time_to", row.time_to)
                row.place_key = payload.get("place_key", row.place_key)
                row.attributes = payload.get("attributes", row.attributes or [])
                row.modality = payload.get("modality", row.modality or "asserted")
                row.polarity = payload.get("polarity", row.polarity or "positive")
                row.source_diversity = int(payload.get("source_diversity", row.source_diversity or 1))
                if incoming_source_point and incoming_source_point != str(row.source_point_id or "").strip():
                    exists_same_source = session.execute(
                        select(KbAssertionEvidenceORM.id).where(
                            KbAssertionEvidenceORM.assertion_id == row.id,
                            KbAssertionEvidenceORM.source_point_id == incoming_source_point,
                        ).limit(1)
                    ).scalar_one_or_none()
                    if exists_same_source is None:
                        row.source_diversity = int((row.source_diversity or 1) + 1)
                if int(payload.get("source_diversity_increment") or 0) > 0:
                    row.source_diversity = int((row.source_diversity or 1) + int(payload.get("source_diversity_increment") or 0))
                row.source_time = payload.get("source_time", row.source_time)
                row.ingest_time = payload.get("ingest_time", row.ingest_time or now)
                row.status = payload.get("status", row.status or "active")
            else:
                created = True
                row = KbAssertionORM(
                    kb_id=kb_id,
                    source_point_id=payload["source_point_id"],
                    source_document_title=payload.get("source_document_title"),
                    source_sentence_id=payload.get("source_sentence_id"),
                    assertion_primary_subject_mention_id=payload.get("assertion_primary_subject_mention_id"),
                    subject_resolution_type=payload.get("subject_resolution_type") or "explicit",
                    subject_entity_id=payload.get("subject_entity_id"),
                    predicate=payload["predicate"],
                    object_entity_id=payload.get("object_entity_id"),
                    object_value=payload.get("object_value"),
                    time_interval_id=payload.get("time_interval_id"),
                    place_id=payload.get("place_id"),
                    time_from=payload.get("time_from"),
                    time_to=payload.get("time_to"),
                    place_key=payload.get("place_key"),
                    attributes=payload.get("attributes") or [],
                    modality=payload.get("modality") or "asserted",
                    polarity=payload.get("polarity") or "positive",
                    canonical_text=payload.get("canonical_text") or "",
                    confidence=float(payload.get("confidence") or 0.0),
                    strength=float(payload.get("strength") or 0.05),
                    baseline_strength=float(payload.get("baseline_strength") or 0.05),
                    decay_rate=float(payload.get("decay_rate") or 0.015),
                    reinforcement_count=int(payload.get("reinforcement_count") or 0),
                    evidence_count=int(payload.get("evidence_count") or 1),
                    source_diversity=int(payload.get("source_diversity") or 1),
                    first_seen_at=payload.get("first_seen_at") or now,
                    last_reinforced_at=payload.get("last_reinforced_at") or now,
                    source_time=payload.get("source_time"),
                    ingest_time=payload.get("ingest_time") or now,
                    status=payload.get("status") or "active",
                    assertion_fingerprint=fingerprint,
                    qdrant_point_id=payload.get("qdrant_point_id"),
                )
                session.add(row)

            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "kb_id": row.kb_id,
                "source_point_id": row.source_point_id,
                "source_sentence_id": row.source_sentence_id,
                "assertion_primary_subject_mention_id": row.assertion_primary_subject_mention_id,
                "subject_resolution_type": row.subject_resolution_type,
                "subject_entity_id": row.subject_entity_id,
                "predicate": row.predicate,
                "object_entity_id": row.object_entity_id,
                "object_value": row.object_value,
                "time_interval_id": row.time_interval_id,
                "place_id": row.place_id,
                "time_from": row.time_from,
                "time_to": row.time_to,
                "place_key": row.place_key,
                "attributes": row.attributes or [],
                "modality": row.modality,
                "polarity": row.polarity,
                "canonical_text": row.canonical_text,
                "confidence": row.confidence,
                "strength": row.strength,
                "baseline_strength": row.baseline_strength,
                "decay_rate": row.decay_rate,
                "reinforcement_count": row.reinforcement_count,
                "evidence_count": row.evidence_count,
                "source_diversity": row.source_diversity,
                "source_time": row.source_time,
                "ingest_time": row.ingest_time,
                "assertion_fingerprint": row.assertion_fingerprint,
                "created": created,
            }

    def add_assertion_evidence(
        self,
        kb_id: int,
        assertion_id: int,
        sentence_id: int,
        source_point_id: str,
        evidence_type: str = "PRIMARY",
        confidence: float | None = None,
        weight: float = 1.0,
    ) -> None:
        with self.session_factory() as session:
            exists = session.execute(
                select(KbAssertionEvidenceORM.id).where(
                    KbAssertionEvidenceORM.assertion_id == assertion_id,
                    KbAssertionEvidenceORM.sentence_id == sentence_id,
                )
            ).scalar_one_or_none()
            if not exists:
                session.add(
                    KbAssertionEvidenceORM(
                        kb_id=kb_id,
                        assertion_id=assertion_id,
                        sentence_id=sentence_id,
                        source_point_id=source_point_id,
                        evidence_type=(evidence_type or "PRIMARY"),
                        confidence=confidence,
                        weight=weight,
                    )
                )
                session.commit()

    def add_reinforcement_event(
        self,
        kb_id: int,
        target_type: str,
        target_id: int,
        event_type: str,
        weight: float = 1.0,
    ) -> None:
        with self.session_factory() as session:
            session.add(
                KbReinforcementEventORM(
                    kb_id=kb_id,
                    target_type=target_type,
                    target_id=target_id,
                    event_type=event_type,
                    weight=weight,
                )
            )
            session.commit()

    def add_assertion_relation(
        self,
        kb_id: int,
        from_assertion_id: int,
        to_assertion_id: int,
        relation_type: str,
        weight: float = 1.0,
        relation_confidence: float | None = None,
    ) -> None:
        with self.session_factory() as session:
            exists = session.execute(
                select(KbAssertionRelationORM.id).where(
                    KbAssertionRelationORM.kb_id == kb_id,
                    KbAssertionRelationORM.from_assertion_id == from_assertion_id,
                    KbAssertionRelationORM.to_assertion_id == to_assertion_id,
                    KbAssertionRelationORM.relation_type == relation_type,
                )
            ).scalar_one_or_none()
            if exists is not None:
                return
            session.add(
                KbAssertionRelationORM(
                    kb_id=kb_id,
                    from_assertion_id=from_assertion_id,
                    to_assertion_id=to_assertion_id,
                    relation_type=relation_type,
                    weight=weight,
                    relation_confidence=float(
                        relation_confidence
                        if relation_confidence is not None
                        else compute_relation_confidence(relation_weight=float(weight))
                    ),
                )
            )
            session.commit()

    def create_assertion_relations_batch(self, kb_id: int, rows: List[dict]) -> int:
        if not rows:
            return 0
        inserted = 0
        with self.session_factory() as session:
            for row in rows:
                from_id = int(row.get("from_assertion_id") or 0)
                to_id = int(row.get("to_assertion_id") or 0)
                relation_type = str(row.get("relation_type") or "").strip()
                if from_id <= 0 or to_id <= 0 or from_id == to_id or not relation_type:
                    continue
                exists = session.execute(
                    select(KbAssertionRelationORM.id).where(
                        KbAssertionRelationORM.kb_id == kb_id,
                        KbAssertionRelationORM.from_assertion_id == from_id,
                        KbAssertionRelationORM.to_assertion_id == to_id,
                        KbAssertionRelationORM.relation_type == relation_type,
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    continue
                session.add(
                    KbAssertionRelationORM(
                        kb_id=kb_id,
                        from_assertion_id=from_id,
                        to_assertion_id=to_id,
                        relation_type=relation_type,
                        weight=float(row.get("weight") or 0.0),
                        relation_confidence=float(
                            row.get("relation_confidence")
                            if row.get("relation_confidence") is not None
                            else compute_relation_confidence(
                                relation_weight=float(row.get("weight") or 0.0),
                                evidence_overlap_count=int(row.get("evidence_overlap_count") or 0),
                                contradiction_signals=int(row.get("contradiction_signals") or 0),
                            )
                        ),
                    )
                )
                inserted += 1
            session.commit()
        return inserted

    def list_assertions_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.source_point_id == source_point_id,
                )
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "predicate": row.predicate,
                    "canonical_text": row.canonical_text,
                    "assertion_fingerprint": row.assertion_fingerprint,
                    "confidence": row.confidence,
                    "strength": row.strength,
                }
                for row in rows
            ]

    def list_mentions_for_assertion(self, assertion_id: int) -> List[dict]:
        with self.session_factory() as session:
            assertion = session.execute(
                select(KbAssertionORM).where(KbAssertionORM.id == assertion_id)
            ).scalar_one_or_none()
            if assertion is None or assertion.source_sentence_id is None:
                return []
            rows = session.execute(
                select(KbMentionORM).where(KbMentionORM.sentence_id == assertion.source_sentence_id)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "sentence_id": row.sentence_id,
                    "surface_form": row.surface_form,
                    "mention_type": row.mention_type,
                    "grammatical_role": row.grammatical_role,
                    "sentence_local_index": row.sentence_local_index,
                    "char_start": row.char_start,
                    "char_end": row.char_end,
                    "resolved_entity_id": row.resolved_entity_id,
                    "resolution_confidence": row.resolution_confidence or 0.0,
                    "is_implicit_subject": bool(row.is_implicit_subject),
                }
                for row in rows
            ]

    def list_sentences_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(KbSentenceORM).where(
                    KbSentenceORM.kb_id == kb_id,
                    KbSentenceORM.source_point_id == source_point_id,
                ).order_by(KbSentenceORM.sentence_order.asc())
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "sentence_order": row.sentence_order,
                    "text": row.text,
                    "sanitized_text": row.sanitized_text,
                    "token_count": row.token_count,
                    "entity_ids": row.entity_ids or [],
                    "assertion_ids": row.assertion_ids or [],
                    "predicate_hints": row.predicate_hints or [],
                    "time_from": row.time_from,
                    "time_to": row.time_to,
                    "place_keys": row.place_keys or [],
                    "qdrant_point_id": row.qdrant_point_id,
                }
                for row in rows
            ]

    def list_chunks_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(KbStructuralChunkORM).where(
                    KbStructuralChunkORM.kb_id == kb_id,
                    KbStructuralChunkORM.source_point_id == source_point_id,
                ).order_by(KbStructuralChunkORM.chunk_order.asc())
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "chunk_order": row.chunk_order,
                    "text": row.text,
                    "sentence_ids": row.sentence_ids or [],
                    "assertion_ids": row.assertion_ids or [],
                    "entity_ids": row.entity_ids or [],
                    "predicate_hints": row.predicate_hints or [],
                    "token_count": row.token_count,
                    "time_from": row.time_from,
                    "time_to": row.time_to,
                    "place_keys": row.place_keys or [],
                    "qdrant_point_id": row.qdrant_point_id,
                }
                for row in rows
            ]

    def list_assertion_evidence(self, assertion_id: int) -> List[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(KbAssertionEvidenceORM).where(KbAssertionEvidenceORM.assertion_id == assertion_id)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "assertion_id": row.assertion_id,
                    "sentence_id": row.sentence_id,
                    "source_point_id": row.source_point_id,
                    "evidence_type": row.evidence_type,
                    "confidence": row.confidence,
                    "weight": row.weight,
                }
                for row in rows
            ]

    def list_assertion_relations(self, assertion_ids: List[int], limit: int = 200) -> List[dict]:
        if not assertion_ids:
            return []
        with self.session_factory() as session:
            rows = session.execute(
                select(KbAssertionRelationORM)
                .where(
                    or_(
                        KbAssertionRelationORM.from_assertion_id.in_(assertion_ids),
                        KbAssertionRelationORM.to_assertion_id.in_(assertion_ids),
                    )
                )
                .order_by(KbAssertionRelationORM.weight.desc(), KbAssertionRelationORM.id.desc())
                .limit(max(1, min(limit, 500)))
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "from_assertion_id": row.from_assertion_id,
                    "to_assertion_id": row.to_assertion_id,
                    "relation_type": row.relation_type,
                    "weight": row.weight,
                    "relation_confidence": row.relation_confidence,
                }
                for row in rows
            ]

    def list_evidence_sentences(self, assertion_ids: List[int], limit: int = 50) -> List[dict]:
        if not assertion_ids:
            return []
        with self.session_factory() as session:
            rows = session.execute(
                select(KbAssertionEvidenceORM, KbSentenceORM)
                .join(KbSentenceORM, KbSentenceORM.id == KbAssertionEvidenceORM.sentence_id)
                .where(KbAssertionEvidenceORM.assertion_id.in_(assertion_ids))
                .order_by(KbAssertionEvidenceORM.weight.desc(), KbAssertionEvidenceORM.id.desc())
                .limit(max(1, min(limit, 300)))
            ).all()
            out: List[dict] = []
            for ev, sent in rows:
                out.append(
                    {
                        "assertion_id": ev.assertion_id,
                        "sentence_id": sent.id,
                        "source_point_id": sent.source_point_id,
                        "text": sent.sanitized_text or sent.text,
                        "entity_ids": sent.entity_ids or [],
                        "assertion_ids": sent.assertion_ids or [],
                        "predicate_hints": sent.predicate_hints or [],
                        "time_from": sent.time_from,
                        "time_to": sent.time_to,
                        "place_keys": sent.place_keys or [],
                        "evidence_type": ev.evidence_type,
                        "evidence_confidence": ev.confidence,
                        "evidence_weight": ev.weight,
                    }
                )
            return out

    def list_chunks_for_sentence_ids(self, sentence_ids: List[int], limit: int = 30) -> List[dict]:
        if not sentence_ids:
            return []
        sentence_set = {int(x) for x in sentence_ids}
        with self.session_factory() as session:
            rows = session.execute(
                select(KbStructuralChunkORM)
                .order_by(KbStructuralChunkORM.id.desc())
                .limit(500)
            ).scalars().all()
            out: List[dict] = []
            for row in rows:
                row_sentence_ids = {int(x) for x in (row.sentence_ids or []) if isinstance(x, int)}
                if not row_sentence_ids.intersection(sentence_set):
                    continue
                out.append(
                    {
                        "chunk_id": row.id,
                        "source_point_id": row.source_point_id,
                        "text": row.text,
                        "sentence_ids": row.sentence_ids or [],
                        "assertion_ids": row.assertion_ids or [],
                        "entity_ids": row.entity_ids or [],
                        "predicate_hints": row.predicate_hints or [],
                        "time_from": row.time_from,
                        "time_to": row.time_to,
                        "place_keys": row.place_keys or [],
                        "token_count": row.token_count,
                    }
                )
                if len(out) >= max(1, min(limit, 200)):
                    break
            return out

    def delete_derived_records_by_source_point_id(self, kb_id: int, source_point_id: str) -> int:
        """Derived rekordok törlése source point alapján (cascade-baráton)."""
        with self.session_factory() as session:
            sentence_ids = session.execute(
                select(KbSentenceORM.id).where(
                    KbSentenceORM.kb_id == kb_id,
                    KbSentenceORM.source_point_id == source_point_id,
                )
            ).scalars().all()
            assertion_ids = session.execute(
                select(KbAssertionORM.id).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.source_point_id == source_point_id,
                )
            ).scalars().all()

            deleted = 0
            if sentence_ids:
                res = session.execute(delete(KbMentionORM).where(KbMentionORM.sentence_id.in_(list(sentence_ids))))
                deleted += int(res.rowcount or 0)
            if assertion_ids:
                res = session.execute(
                    delete(KbAssertionEvidenceORM).where(KbAssertionEvidenceORM.assertion_id.in_(list(assertion_ids)))
                )
                deleted += int(res.rowcount or 0)
                res_rel_from = session.execute(
                    delete(KbAssertionRelationORM).where(KbAssertionRelationORM.from_assertion_id.in_(list(assertion_ids)))
                )
                res_rel_to = session.execute(
                    delete(KbAssertionRelationORM).where(KbAssertionRelationORM.to_assertion_id.in_(list(assertion_ids)))
                )
                deleted += int(res_rel_from.rowcount or 0)
                deleted += int(res_rel_to.rowcount or 0)

            # source_point-hoz kötött táblák
            for model in [
                KbAssertionORM,
                KbStructuralChunkORM,
                KbTimeIntervalORM,
            ]:
                res = session.execute(
                    delete(model).where(
                        model.kb_id == kb_id,
                        model.source_point_id == source_point_id,
                    )
                )
                deleted += int(res.rowcount or 0)

            res = session.execute(
                delete(KbSentenceORM).where(
                    KbSentenceORM.kb_id == kb_id,
                    KbSentenceORM.source_point_id == source_point_id,
                )
            )
            deleted += int(res.rowcount or 0)

            # lazán kapcsolt entitások: csak akkor töröljük, ha nincs más assertion evidence
            orphan_entities = session.execute(
                select(KbEntityORM.id).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.source_point_id == source_point_id,
                )
            ).scalars().all()
            for entity_id in orphan_entities:
                still_used = session.execute(
                    select(KbAssertionORM.id).where(
                        KbAssertionORM.kb_id == kb_id,
                        or_(
                            KbAssertionORM.subject_entity_id == entity_id,
                            KbAssertionORM.object_entity_id == entity_id,
                        ),
                    ).limit(1)
                ).scalar_one_or_none()
                if still_used is None:
                    res_alias = session.execute(delete(KbEntityAliasORM).where(KbEntityAliasORM.entity_id == entity_id))
                    res_entity = session.execute(delete(KbEntityORM).where(KbEntityORM.id == entity_id))
                    deleted += int(res_alias.rowcount or 0)
                    deleted += int(res_entity.rowcount or 0)

            session.commit()
            return deleted

    def search_candidate_assertions(
        self,
        kb_ids: List[int],
        predicates: Optional[List[str]] = None,
        entity_ids: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[dict]:
        if not kb_ids:
            return []
        with self.session_factory() as session:
            conditions = [KbAssertionORM.kb_id.in_(kb_ids)]
            if predicates:
                conditions.append(KbAssertionORM.predicate.in_(predicates))
            if entity_ids:
                conditions.append(
                    or_(
                        KbAssertionORM.subject_entity_id.in_(entity_ids),
                        KbAssertionORM.object_entity_id.in_(entity_ids),
                    )
                )

            stmt = (
                select(KbAssertionORM)
                .where(and_(*conditions))
                .order_by(KbAssertionORM.strength.desc(), KbAssertionORM.confidence.desc(), KbAssertionORM.id.desc())
                .limit(max(1, min(limit, 500)))
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "source_sentence_id": row.source_sentence_id,
                    "subject_entity_id": row.subject_entity_id,
                    "predicate": row.predicate,
                    "object_entity_id": row.object_entity_id,
                    "object_value": row.object_value,
                    "time_from": row.time_from,
                    "time_to": row.time_to,
                    "place_key": row.place_key,
                    "canonical_text": row.canonical_text,
                    "confidence": row.confidence,
                    "strength": row.strength,
                    "baseline_strength": row.baseline_strength,
                    "decay_rate": row.decay_rate,
                    "last_reinforced_at": row.last_reinforced_at,
                    "status": row.status,
                    "assertion_fingerprint": row.assertion_fingerprint,
                }
                for row in rows
            ]

    def search_assertion_candidates(
        self,
        kb_ids: List[int],
        predicates: Optional[List[str]] = None,
        entity_ids: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[dict]:
        return self.search_candidate_assertions(
            kb_ids=kb_ids,
            predicates=predicates,
            entity_ids=entity_ids,
            limit=limit,
        )

    def search_entity_candidates(self, kb_ids: List[int], query: str, limit: int = 20) -> List[dict]:
        if not kb_ids:
            return []
        needle = f"%{(query or '').strip()}%"
        with self.session_factory() as session:
            norm = (query or "").strip().lower()
            rows = session.execute(
                select(KbEntityORM)
                .where(
                    KbEntityORM.kb_id.in_(kb_ids),
                    or_(
                        KbEntityORM.canonical_name.ilike(needle),
                        KbEntityORM.canonical_key.ilike(f"%::{norm}"),
                        KbEntityORM.id.in_(
                            select(KbEntityAliasORM.entity_id).where(
                                or_(
                                    KbEntityAliasORM.alias.ilike(needle),
                                    KbEntityAliasORM.alias_text.ilike(needle),
                                )
                            )
                        ),
                    ),
                )
                .order_by(KbEntityORM.confidence.desc(), KbEntityORM.id.desc())
                .limit(max(1, min(limit, 100)))
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "canonical_name": row.canonical_name,
                    "canonical_key": row.canonical_key,
                    "entity_type": row.entity_type,
                    "aliases": row.aliases or [],
                    "confidence": row.confidence or 0.0,
                }
                for row in rows
            ]

    def get_assertion_neighbors(
        self,
        kb_id: int,
        assertion_ids: List[int],
        max_hops: int = 1,
        allowed_relation_types: Optional[List[str]] = None,
        limit: int = 80,
    ) -> List[dict]:
        if not assertion_ids:
            return []
        frontier = set(int(x) for x in assertion_ids)
        visited = set(frontier)
        edges: list[dict] = []
        with self.session_factory() as session:
            for depth in range(max(1, min(max_hops, 2))):
                rel_conditions = [
                    KbAssertionRelationORM.kb_id == kb_id,
                    or_(
                        KbAssertionRelationORM.from_assertion_id.in_(list(frontier)),
                        KbAssertionRelationORM.to_assertion_id.in_(list(frontier)),
                    ),
                ]
                if allowed_relation_types:
                    rel_conditions.append(KbAssertionRelationORM.relation_type.in_(allowed_relation_types))
                rel_rows = session.execute(
                    select(KbAssertionRelationORM)
                    .where(and_(*rel_conditions))
                    .order_by(KbAssertionRelationORM.weight.desc(), KbAssertionRelationORM.id.desc())
                    .limit(max(1, min(limit * 3, 500)))
                ).scalars().all()
                next_frontier: set[int] = set()
                for rel in rel_rows:
                    other_id = rel.to_assertion_id if rel.from_assertion_id in frontier else rel.from_assertion_id
                    if other_id in visited:
                        continue
                    edges.append(
                        {
                            "neighbor_assertion_id": int(other_id),
                            "relation_type": rel.relation_type,
                            "relation_weight": rel.weight,
                            "relation_confidence": rel.relation_confidence,
                            "relation_current_weight": _current_relation_weight(
                                weight=float(rel.weight or 0.0),
                                relation_type=str(rel.relation_type or ""),
                                created_at=rel.created_at,
                            ),
                            "relation_created_at": rel.created_at,
                            "depth": depth + 1,
                        }
                    )
                    next_frontier.add(int(other_id))
                    visited.add(int(other_id))
                    if len(edges) >= limit:
                        break
                frontier = next_frontier
                if not frontier or len(edges) >= limit:
                    break
            if not edges:
                return []
            assertions = session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.id.in_([x["neighbor_assertion_id"] for x in edges]),
                )
            ).scalars().all()
            by_id = {row.id: row for row in assertions}
            out: List[dict] = []
            for edge in edges:
                row = by_id.get(int(edge["neighbor_assertion_id"]))
                if row is None:
                    continue
                out.append(
                    {
                        "assertion_id": row.id,
                        "canonical_text": row.canonical_text,
                        "predicate": row.predicate,
                        "source_point_id": row.source_point_id,
                        "time_from": row.time_from,
                        "time_to": row.time_to,
                        "place_key": row.place_key,
                        "subject_entity_id": row.subject_entity_id,
                        "object_entity_id": row.object_entity_id,
                        "relation_type": edge["relation_type"],
                        "relation_weight": edge["relation_weight"],
                        "relation_confidence": edge.get("relation_confidence"),
                        "relation_current_weight": edge.get("relation_current_weight"),
                        "relation_created_at": edge.get("relation_created_at"),
                        "depth": edge["depth"],
                        "confidence": row.confidence,
                        "strength": row.strength,
                        "baseline_strength": row.baseline_strength,
                        "decay_rate": row.decay_rate,
                        "last_reinforced_at": row.last_reinforced_at,
                        "status": row.status,
                    }
                )
                if len(out) >= limit:
                    break
            return out

    def get_allowed_kb_ids_for_user(self, user_id: int) -> List[int]:
        return self.get_kb_ids_with_permission(user_id, "use")

    def get_assertion_by_id(self, kb_id: int, assertion_id: int) -> Optional[dict]:
        with self.session_factory() as session:
            row = session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.id == assertion_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "kb_id": row.kb_id,
                "source_point_id": row.source_point_id,
                "source_sentence_id": row.source_sentence_id,
                "assertion_primary_subject_mention_id": row.assertion_primary_subject_mention_id,
                "subject_resolution_type": row.subject_resolution_type,
                "subject_entity_id": row.subject_entity_id,
                "object_entity_id": row.object_entity_id,
                "time_from": row.time_from,
                "time_to": row.time_to,
                "place_key": row.place_key,
                "predicate": row.predicate,
                "confidence": row.confidence,
                "strength": row.strength,
                "baseline_strength": row.baseline_strength,
                "decay_rate": row.decay_rate,
                "evidence_count": row.evidence_count,
                "source_diversity": row.source_diversity,
                "last_reinforced_at": row.last_reinforced_at,
                "status": row.status,
                "canonical_text": row.canonical_text,
                "assertion_fingerprint": row.assertion_fingerprint,
            }

    def update_assertion_strength(
        self,
        kb_id: int,
        assertion_id: int,
        strength: float,
        last_reinforced_at: Optional[datetime] = None,
        reinforcement_increment: int = 0,
    ) -> bool:
        with self.session_factory() as session:
            row = session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.id == assertion_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.strength = float(strength)
            if last_reinforced_at is not None:
                row.last_reinforced_at = last_reinforced_at
            if reinforcement_increment > 0:
                row.reinforcement_count = int((row.reinforcement_count or 0) + reinforcement_increment)
            session.commit()
            return True

    def update_assertion_status(self, kb_id: int, assertion_id: int, status: str) -> bool:
        with self.session_factory() as session:
            row = session.execute(
                select(KbAssertionORM).where(
                    KbAssertionORM.kb_id == kb_id,
                    KbAssertionORM.id == assertion_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.status = str(status or "active").strip().lower()
            session.commit()
            return True

    def list_assertions_for_kb(self, kb_id: int, limit: int = 1000, offset: int = 0) -> List[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(KbAssertionORM)
                .where(KbAssertionORM.kb_id == kb_id)
                .order_by(KbAssertionORM.id.asc())
                .limit(max(1, min(limit, 20000)))
                .offset(max(0, offset))
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "kb_id": row.kb_id,
                    "source_point_id": row.source_point_id,
                    "subject_entity_id": row.subject_entity_id,
                    "object_entity_id": row.object_entity_id,
                    "predicate": row.predicate,
                    "status": row.status,
                    "confidence": row.confidence,
                    "evidence_count": row.evidence_count,
                    "source_diversity": row.source_diversity,
                    "strength": row.strength,
                    "baseline_strength": row.baseline_strength,
                    "decay_rate": row.decay_rate,
                    "last_reinforced_at": row.last_reinforced_at,
                }
                for row in rows
            ]

    def get_assertion_debug(self, kb_id: int, assertion_id: int) -> dict:
        assertion = self.get_assertion_by_id(kb_id, assertion_id)
        if not assertion:
            return {}
        return {
            "assertion": assertion,
            "relations": self.list_assertion_relations([assertion_id], limit=200),
            "evidence": self.list_assertion_evidence(assertion_id),
            "mentions": self.list_mentions_for_assertion(assertion_id),
        }

    def get_entity_debug(self, kb_id: int, entity_id: int) -> dict:
        with self.session_factory() as session:
            entity = session.execute(
                select(KbEntityORM).where(
                    KbEntityORM.kb_id == kb_id,
                    KbEntityORM.id == entity_id,
                )
            ).scalar_one_or_none()
            if entity is None:
                return {}
            aliases = session.execute(
                select(KbEntityAliasORM.alias).where(KbEntityAliasORM.entity_id == entity_id)
            ).scalars().all()
            linked = session.execute(
                select(KbAssertionORM.id).where(
                    KbAssertionORM.kb_id == kb_id,
                    or_(
                        KbAssertionORM.subject_entity_id == entity_id,
                        KbAssertionORM.object_entity_id == entity_id,
                    ),
                )
            ).scalars().all()
            return {
                "entity": {
                    "id": entity.id,
                    "canonical_name": entity.canonical_name,
                    "canonical_key": entity.canonical_key,
                    "entity_type": entity.entity_type,
                    "confidence": entity.confidence,
                    "aliases": list(aliases or []),
                },
                "assertion_ids": [int(x) for x in linked],
                "assertion_count": len(linked),
            }

    def get_source_point_debug(self, kb_id: int, source_point_id: str) -> dict:
        assertions = self.list_assertions_by_source_point_id(kb_id=kb_id, source_point_id=source_point_id)
        sentences = self.list_sentences_by_source_point_id(kb_id=kb_id, source_point_id=source_point_id)
        chunks = self.list_chunks_by_source_point_id(kb_id=kb_id, source_point_id=source_point_id)
        return {
            "source_point_id": source_point_id,
            "assertions": assertions,
            "sentences": sentences,
            "chunks": chunks,
            "counts": {
                "assertions": len(assertions),
                "sentences": len(sentences),
                "chunks": len(chunks),
            },
        }

    def get_relation_bundle(self, kb_id: int, assertion_id: int, limit: int = 60) -> dict:
        rows = self.get_assertion_neighbors(
            kb_id=kb_id,
            assertion_ids=[assertion_id],
            max_hops=2,
            allowed_relation_types=None,
            limit=limit,
        )
        by_type: dict[str, int] = {}
        for row in rows:
            rel = str(row.get("relation_type") or "UNKNOWN")
            by_type[rel] = by_type.get(rel, 0) + 1
        return {
            "assertion_id": assertion_id,
            "neighbors": rows,
            "relation_counts": by_type,
        }

    def get_metric_snapshot(self, kb_id: int) -> dict:
        rows = self.list_assertions_for_kb(kb_id=kb_id, limit=20000, offset=0)
        status_counts: dict[str, int] = {}
        relation_counts: dict[str, int] = {}
        with self.session_factory() as session:
            rel_rows = session.execute(
                select(KbAssertionRelationORM.relation_type)
                .where(KbAssertionRelationORM.kb_id == kb_id)
            ).all()
        for status in [str(x.get("status") or "active") for x in rows]:
            status_counts[status] = status_counts.get(status, 0) + 1
        for rel in [str(x[0] or "UNKNOWN") for x in rel_rows]:
            relation_counts[rel] = relation_counts.get(rel, 0) + 1
        total = len(rows) or 1
        avg_ev = sum(float(x.get("evidence_count") or 0.0) for x in rows) / total
        avg_div = sum(float(x.get("source_diversity") or 0.0) for x in rows) / total
        avg_strength = sum(float(x.get("strength") or 0.0) for x in rows) / total
        return {
            "assertion_count": len(rows),
            "status_counts": status_counts,
            "relation_type_counts": relation_counts,
            "avg_evidence_count": avg_ev,
            "avg_source_diversity": avg_div,
            "avg_strength": avg_strength,
        }
