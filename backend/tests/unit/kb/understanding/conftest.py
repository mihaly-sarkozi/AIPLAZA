"""Közös in-memory fake-ek a kb_understanding unit tesztekhez."""
from __future__ import annotations

from typing import Any

import pytest

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext


class FakeContentRepository:
    def __init__(self) -> None:
        self.extracted: dict[str, Any] = {}
        self.normalized: dict[str, Any] = {}

    def replace_extracted(self, training_item_id: str, content) -> None:
        self.extracted[training_item_id] = content

    def replace_normalized(self, training_item_id: str, content) -> None:
        self.normalized[training_item_id] = content

    def get_extracted_for_item(self, training_item_id: str):
        return self.extracted.get(training_item_id)

    def get_normalized_for_item(self, training_item_id: str):
        return self.normalized.get(training_item_id)


class FakeStructureRepository:
    def __init__(self) -> None:
        self.blocks: dict[str, list] = {}

    def replace_for_item(self, training_item_id: str, blocks: list) -> int:
        self.blocks[training_item_id] = list(blocks)
        return len(blocks)

    def list_for_item(self, training_item_id: str) -> list:
        return list(self.blocks.get(training_item_id, []))


class FakeChunkRepository:
    def __init__(self) -> None:
        self.chunks: dict[str, list] = {}
        self.versions: dict[str, int] = {}

    def replace_for_document(self, document_id: str, chunks: list) -> int:
        self.chunks[document_id] = list(chunks)
        if chunks:
            self.versions[document_id] = max(int(getattr(c, "version", 1) or 1) for c in chunks)
        return len(chunks)

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


class FakeStepRunRepository:
    def __init__(self) -> None:
        self.runs: list = []

    def add_run(self, job_id: str, result) -> str:
        self.runs.append((job_id, result))
        return f"run_{len(self.runs)}"

    def list_for_job(self, job_id: str) -> list:
        return [result for run_job_id, result in self.runs if run_job_id == job_id]


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
