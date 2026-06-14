from __future__ import annotations

from sqlalchemy import desc, select

from apps.kb.kb_indexing.enums.IndexVerificationStatus import IndexVerificationStatus
from apps.kb.kb_indexing.orm.IndexVerification import IndexVerification
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class IndexVerificationRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        indexing_job_id: str,
        collection_name: str,
        expected_points: int,
    ) -> IndexVerification:
        now = utc_now_naive()
        row = IndexVerification(
            id=new_id("idx_verify"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            indexing_job_id=indexing_job_id,
            status=IndexVerificationStatus.RUNNING.value,
            collection_name=collection_name,
            expected_points=expected_points,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
        return row

    def finish(
        self,
        verification_id: str,
        *,
        status: IndexVerificationStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        verified_points: int = 0,
        missing_points: int = 0,
        payload_mismatches: int = 0,
        vector_hash_mismatches: int = 0,
        failed_points: int = 0,
        metadata: dict | None = None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(IndexVerification, verification_id)
            if row is None:
                return
            row.status = status.value
            row.error_code = error_code
            row.error_message = (error_message or "")[:4000] or None
            row.verified_points = verified_points
            row.missing_points = missing_points
            row.payload_mismatches = payload_mismatches
            row.vector_hash_mismatches = vector_hash_mismatches
            row.failed_points = failed_points
            row.finished_at = utc_now_naive()
            row.updated_at = utc_now_naive()
            if metadata:
                row.metadata_json = dict(metadata)
            session.commit()

    def get(self, verification_id: str) -> IndexVerification | None:
        with self._session_factory() as session:
            row = session.get(IndexVerification, verification_id)
            if row is not None:
                session.expunge(row)
            return row

    def get_latest_for_indexing_job(self, indexing_job_id: str) -> IndexVerification | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(IndexVerification)
                    .where(IndexVerification.indexing_job_id == indexing_job_id)
                    .order_by(desc(IndexVerification.created_at))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row

    def get_latest_for_training_item(self, training_item_id: str) -> IndexVerification | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(IndexVerification)
                    .where(IndexVerification.training_item_id == training_item_id)
                    .order_by(desc(IndexVerification.created_at))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row


__all__ = ["IndexVerificationRepository"]
