from __future__ import annotations

from sqlalchemy import func, select, text

from apps.kb.kb_processing.orm.ProcessingMetrics import ProcessingMetrics
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class ProcessingMetricsRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get_for_knowledge_base(self, knowledge_base_id: str) -> ProcessingMetrics | None:
        with self._session_factory() as session:
            row = session.execute(
                select(ProcessingMetrics).where(ProcessingMetrics.knowledge_base_id == knowledge_base_id)
            ).scalar_one_or_none()
            if row is not None:
                session.expunge(row)
            return row

    def upsert(self, metrics: ProcessingMetrics) -> ProcessingMetrics:
        with self._session_factory() as session:
            existing = session.execute(
                select(ProcessingMetrics).where(
                    ProcessingMetrics.knowledge_base_id == metrics.knowledge_base_id
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(metrics)
            else:
                for column in ProcessingMetrics.__table__.columns:
                    name = column.name
                    if name in {"id", "knowledge_base_id"}:
                        continue
                    setattr(existing, name, getattr(metrics, name))
            session.commit()
            target = existing or metrics
            session.refresh(target)
            session.expunge(target)
            return target

    def aggregate_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None,
        issue_counts: dict[str, int],
    ) -> ProcessingMetrics:
        existing = self.get_for_knowledge_base(knowledge_base_id)
        preserved_metadata = dict(existing.metadata_json or {}) if existing is not None else {}

        with self._session_factory() as session:
            items_total = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_ingest_items WHERE knowledge_base_id = :kb_id"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            batches_total = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_ingest_batches WHERE knowledge_base_id = :kb_id"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            understanding_ready = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_understanding_jobs "
                        "WHERE knowledge_base_id = :kb_id AND status = 'ready_for_discovery'"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            understanding_partial = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_understanding_jobs "
                        "WHERE knowledge_base_id = :kb_id AND status = 'partial'"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            understanding_failed = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_understanding_jobs "
                        "WHERE knowledge_base_id = :kb_id AND status IN ('failed', 'retryable')"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            discovery_ready = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_discovery_jobs "
                        "WHERE knowledge_base_id = :kb_id AND status = 'ready_for_embedding'"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            chunks_total = int(
                session.execute(
                    text("SELECT COUNT(*) FROM kb_chunks WHERE knowledge_base_id = :kb_id"),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            extracted_parts_total = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_extracted_content_parts "
                        "WHERE knowledge_base_id = :kb_id"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            normalized_parts_total = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_normalized_content_parts "
                        "WHERE knowledge_base_id = :kb_id"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            last_ingested_at = session.execute(
                text(
                    "SELECT MAX(created_at) FROM kb_ingest_items WHERE knowledge_base_id = :kb_id"
                ),
                {"kb_id": knowledge_base_id},
            ).scalar_one()
            last_processed_at = session.execute(
                text(
                    "SELECT MAX(completed_at) FROM kb_understanding_jobs "
                    "WHERE knowledge_base_id = :kb_id AND completed_at IS NOT NULL"
                ),
                {"kb_id": knowledge_base_id},
            ).scalar_one()
            last_failed_at = session.execute(
                text(
                    "SELECT MAX(completed_at) FROM kb_understanding_jobs "
                    "WHERE knowledge_base_id = :kb_id AND status IN ('failed', 'retryable')"
                ),
                {"kb_id": knowledge_base_id},
            ).scalar_one()
            documents_ingested = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM kb_ingest_items "
                        "WHERE knowledge_base_id = :kb_id AND status = 'accepted'"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
            )
            documents_indexed = int(
                session.execute(
                    text(
                        "SELECT COUNT(DISTINCT training_item_id) FROM kb_indexing_jobs "
                        "WHERE knowledge_base_id = :kb_id AND status IN ('COMPLETED', 'PARTIAL')"
                    ),
                    {"kb_id": knowledge_base_id},
                ).scalar_one()
                or 0
            )
            last_indexed_at = session.execute(
                text(
                    "SELECT MAX(finished_at) FROM kb_indexing_jobs "
                    "WHERE knowledge_base_id = :kb_id AND finished_at IS NOT NULL"
                ),
                {"kb_id": knowledge_base_id},
            ).scalar_one()

        open_total = sum(issue_counts.values())
        return ProcessingMetrics(
            id=existing.id if existing is not None else new_id("proc_metrics"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            documents_total=items_total,
            documents_ingested=documents_ingested,
            documents_understanding_ready=understanding_ready,
            documents_discovery_ready=discovery_ready,
            documents_indexed=documents_indexed,
            documents_failed=understanding_failed,
            documents_partial=understanding_partial,
            batches_total=batches_total,
            items_total=items_total,
            extracted_parts_total=extracted_parts_total,
            normalized_parts_total=normalized_parts_total,
            chunks_total=chunks_total,
            issues_open=open_total,
            issues_warning=int(issue_counts.get("WARNING", 0)),
            issues_error=int(issue_counts.get("ERROR", 0)),
            issues_critical=int(issue_counts.get("CRITICAL", 0)),
            last_ingested_at=last_ingested_at,
            last_processed_at=last_processed_at,
            last_failed_at=last_failed_at,
            last_indexed_at=last_indexed_at,
            metadata_json=preserved_metadata,
            updated_at=utc_now_naive(),
        )


__all__ = ["ProcessingMetricsRepository"]
