from __future__ import annotations

from sqlalchemy import desc, select

from apps.kb.kb_indexing.enums.IndexRebuildStatus import IndexRebuildStatus, TERMINAL_REBUILD_STATUSES
from apps.kb.kb_indexing.orm.IndexRebuild import IndexRebuild
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class IndexRebuildRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        mode: str,
        requested_by: int | None,
        reason: str | None,
        training_items_total: int = 0,
        metadata: dict | None = None,
    ) -> IndexRebuild:
        row = IndexRebuild(
            id=new_id("idx_rebuild"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            status=IndexRebuildStatus.PENDING.value,
            mode=mode,
            requested_by=requested_by,
            reason=(reason or "")[:4000] or None,
            training_items_total=training_items_total,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
        return row

    def get(self, rebuild_id: str) -> IndexRebuild | None:
        with self._session_factory() as session:
            row = session.get(IndexRebuild, rebuild_id)
            if row is not None:
                session.expunge(row)
            return row

    def has_active_for_knowledge_base(self, knowledge_base_id: str) -> str | None:
        terminal = [status.value for status in TERMINAL_REBUILD_STATUSES]
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(IndexRebuild.id)
                    .where(
                        IndexRebuild.knowledge_base_id == knowledge_base_id,
                        IndexRebuild.status.notin_(terminal),
                    )
                    .order_by(desc(IndexRebuild.created_at))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return row

    def mark_running(self, rebuild_id: str) -> None:
        now = utc_now_naive()
        with self._session_factory() as session:
            row = session.get(IndexRebuild, rebuild_id)
            if row is None:
                return
            row.status = IndexRebuildStatus.RUNNING.value
            row.started_at = now
            row.updated_at = now
            session.commit()

    def finish(
        self,
        rebuild_id: str,
        *,
        status: IndexRebuildStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        training_items_reindexed: int | None = None,
        training_items_failed: int | None = None,
        points_deleted: int | None = None,
        points_reindexed: int | None = None,
        points_verified: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        now = utc_now_naive()
        with self._session_factory() as session:
            row = session.get(IndexRebuild, rebuild_id)
            if row is None:
                return
            row.status = status.value
            row.finished_at = now
            row.error_code = error_code
            row.error_message = (error_message or "")[:4000] or None
            if training_items_reindexed is not None:
                row.training_items_reindexed = training_items_reindexed
            if training_items_failed is not None:
                row.training_items_failed = training_items_failed
            if points_deleted is not None:
                row.points_deleted = points_deleted
            if points_reindexed is not None:
                row.points_reindexed = points_reindexed
            if points_verified is not None:
                row.points_verified = points_verified
            if metadata:
                row.metadata_json = {**(row.metadata_json or {}), **metadata}
            row.updated_at = now
            session.commit()


__all__ = ["IndexRebuildRepository"]
