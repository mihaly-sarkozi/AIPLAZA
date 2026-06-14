"""Közös in-memory fake-ek a kb_understanding unit tesztekhez."""
from __future__ import annotations

from typing import Any

import pytest

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext


class FakeContentRepository:
    def __init__(self) -> None:
        self.extracted: dict[str, Any] = {}
        self.normalized: dict[str, Any] = {}
        self.normalized_parts: dict[str, list] = {}
        self.parts: dict[str, list] = {}

    def begin_extract(self, training_item_id: str, content) -> None:
        self.extracted[training_item_id] = content
        self.parts[training_item_id] = []

    def bulk_insert_parts(self, parts: list) -> None:
        if parts:
            item_id = parts[0].training_item_id
            self.parts.setdefault(item_id, []).extend(parts)

    def finalize_extract(self, extracted_content_id: str, *, patch: dict) -> None:
        for content in self.extracted.values():
            if getattr(content, "id", None) == extracted_content_id:
                for key, value in patch.items():
                    if hasattr(content, key):
                        setattr(content, key, value)

    def replace_extracted_with_parts(
        self,
        training_item_id: str,
        content,
        parts: list,
        *,
        batch_size: int = 50,
    ) -> None:
        self.extracted[training_item_id] = content
        self.parts[training_item_id] = list(parts)

    def replace_extracted(self, training_item_id: str, content) -> None:
        self.extracted[training_item_id] = content

    def delete_normalized_by_training_item(self, training_item_id: str) -> None:
        self.normalized.pop(training_item_id, None)
        self.normalized_parts.pop(training_item_id, None)

    def create_normalized_summary(self, content) -> None:
        self.normalized[content.training_item_id] = content

    def bulk_insert_normalized_parts(self, parts: list) -> None:
        if not parts:
            return
        item_id = parts[0].training_item_id
        self.normalized_parts.setdefault(item_id, []).extend(parts)

    def finalize_normalized_summary(self, normalized_content_id: str, *, patch: dict) -> None:
        for content in self.normalized.values():
            if getattr(content, "id", None) == normalized_content_id:
                for key, value in patch.items():
                    if key == "metadata_json":
                        metadata = dict(getattr(content, "metadata_json", None) or {})
                        metadata.update(value)
                        content.metadata_json = metadata
                    elif hasattr(content, key):
                        setattr(content, key, value)

    def iter_normalizable_extracted_parts(
        self,
        training_item_id: str,
        *,
        batch_size: int = 100,
        part_types=None,
    ):
        rows = self.list_parts_for_item(training_item_id, part_types=part_types, completed_only=True)
        for index in range(0, len(rows), batch_size):
            yield rows[index : index + batch_size]

    def iter_normalized_parts_for_item(self, training_item_id: str, *, batch_size: int = 100):
        rows = sorted(
            self.normalized_parts.get(training_item_id, []),
            key=lambda row: (
                getattr(row, "document_order", None),
                getattr(row, "page_number", None),
                getattr(row, "part_index", 0),
            ),
        )
        for index in range(0, len(rows), batch_size):
            yield rows[index : index + batch_size]

    def count_normalizable_extracted_parts(self, training_item_id: str) -> int:
        return len(self.list_parts_for_item(training_item_id, completed_only=True))

    def count_normalized_parts(self, training_item_id: str) -> int:
        return sum(
            1
            for row in self.normalized_parts.get(training_item_id, [])
            if getattr(row, "status", "completed") == "completed"
            and (getattr(row, "normalized_text", "") or "").strip()
        )

    def get_extracted_for_item(self, training_item_id: str):
        return self.extracted.get(training_item_id)

    def get_normalized_for_item(self, training_item_id: str):
        return self.normalized.get(training_item_id)

    def list_parts_for_item(self, training_item_id: str, *, part_types=None, completed_only=True):
        rows = list(self.parts.get(training_item_id, []))
        if part_types:
            rows = [row for row in rows if getattr(row, "part_type", None) in part_types]
        if completed_only:
            rows = [row for row in rows if getattr(row, "status", "completed") == "completed"]
        return rows

    def count_usable_parts(self, training_item_id: str) -> int:
        return len(
            [
                row
                for row in self.parts.get(training_item_id, [])
                if (getattr(row, "text", "") or "").strip()
            ]
        )
class FakeChunkRepository:
    def __init__(self) -> None:
        self.chunks: dict[str, list] = {}
        self.versions: dict[str, int] = {}

    def replace_for_document(self, document_id: str, chunks, *, batch_size: int = 100) -> int:
        rows = list(chunks)
        self.chunks[document_id] = rows
        if rows:
            self.versions[document_id] = max(int(getattr(c, "version", 1) or 1) for c in rows)
        return len(rows)

    def list_for_document(self, document_id: str) -> list:
        return list(self.chunks.get(document_id, []))

    def count_for_document(self, document_id: str) -> int:
        return len(self.chunks.get(document_id, []))

    def max_version_for_document(self, document_id: str) -> int:
        return self.versions.get(document_id, 0)


class FakeEntityRepository:
    def __init__(self) -> None:
        self.entities: dict[str, list] = {}

    def replace_for_document(self, document_id: str, entities: list) -> int:
        self.entities[document_id] = list(entities)
        return len(entities)

    def list_for_document(self, document_id: str) -> list:
        return list(self.entities.get(document_id, []))

    def count_for_document(self, document_id: str) -> int:
        return len(self.entities.get(document_id, []))


class FakeEnrichmentRepository:
    def __init__(self) -> None:
        self.rows: list = []

    def replace_for_chunks(self, chunk_ids: list[str], enrichments: list) -> int:
        self.rows = list(enrichments)
        return len(enrichments)

    def list_for_chunks(self, chunk_ids: list[str]) -> list:
        return list(self.rows)


class FakeEmbeddingRepository:
    def __init__(self) -> None:
        self.rows: list = []

    def replace_for_chunks(self, chunk_ids: list[str], embeddings: list) -> int:
        self.rows = list(embeddings)
        return len(embeddings)

    def count_for_chunks(self, chunk_ids: list[str]) -> int:
        return sum(1 for row in self.rows if row.chunk_id in set(chunk_ids))


class FakeRelationshipRepository:
    def __init__(self) -> None:
        self.rows: list = []

    def replace_for_job(self, job_id: str, relationships: list) -> int:
        self.rows = list(relationships)
        return len(relationships)

    def list_for_job(self, job_id: str) -> list:
        return list(self.rows)


class FakeScoreRepository:
    def __init__(self) -> None:
        self.rows: list = []

    def replace_for_chunks(self, chunk_ids: list[str], scores: list) -> int:
        self.rows = list(scores)
        return len(scores)

    def list_for_chunks(self, chunk_ids: list[str]) -> list:
        return list(self.rows)


class FakeJobRepository:
    def __init__(self) -> None:
        self.status_history: list[str] = []
        self.completed: tuple | None = None
        self.failed: dict | None = None

    def set_status(self, job_id: str, status) -> None:
        self.status_history.append(status.value)

    def mark_completed(self, job_id: str, status) -> None:
        self.completed = (job_id, status.value)

    def mark_failed(self, job_id: str, *, status, error_code, error_message=None, retryable=False) -> None:
        self.failed = {
            "job_id": job_id,
            "status": status.value,
            "error_code": error_code,
            "error_message": error_message,
            "retryable": retryable,
        }


class FakeFlowRecorder:
    def __init__(self) -> None:
        self.started: list[dict] = []
        self.completed: list[dict] = []
        self.failed: list[dict] = []
        self.issues: list[dict] = []

    def record_stage_started(self, ctx, **kwargs) -> None:
        self.started.append(kwargs)

    def record_stage_completed(self, ctx, **kwargs) -> None:
        self.completed.append(kwargs)

    def record_stage_failed(self, ctx, **kwargs) -> None:
        self.failed.append(kwargs)

    def open_issue(self, ctx, **kwargs) -> None:
        self.issues.append(kwargs)

    def recalculate_metrics(self, ctx) -> None:
        return None


@pytest.fixture
def ctx() -> UnderstandingJobContext:
    return UnderstandingJobContext(
        job_id="und_job_1",
        training_item_id="training_item_1",
        training_batch_id="training_batch_1",
        knowledge_base_id="kb-uuid-1",
        tenant_slug="tenant1",
        created_by=1,
        raw_ref="tenants/tenant1/kb/kb-uuid-1/training/b/i/input.txt",
        mime_type="text/plain",
        source_type="text",
        file_name=None,
        title="Teszt anyag",
        content_hash="hash123",
    )
