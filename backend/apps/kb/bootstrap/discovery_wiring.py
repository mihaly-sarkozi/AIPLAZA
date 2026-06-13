from __future__ import annotations

from apps.kb.shared.contracts import DiscoveryChunkSnapshot


class ChunkReaderAdapter:
    def __init__(self, chunk_repository) -> None:
        self._chunk_repository = chunk_repository

    def list_for_document(self, document_id: str) -> list[DiscoveryChunkSnapshot]:
        chunks = self._chunk_repository.list_for_document(document_id)
        return [
            DiscoveryChunkSnapshot(
                chunk_id=chunk.id,
                text=chunk.text,
                chunk_type=str(chunk.chunk_type or "paragraph"),
                order_index=int(chunk.order_index or 0),
                section_title=chunk.section_title,
                page_number=chunk.page_number,
            )
            for chunk in chunks
        ]


class UnderstandingJobReaderAdapter:
    def __init__(self, job_repository) -> None:
        self._job_repository = job_repository

    def get_job(self, job_id: str) -> dict | None:
        job = self._job_repository.get_job(job_id)
        if job is None:
            return None
        metadata = dict(job.metadata_json or {})
        return {
            "id": job.id,
            "training_item_id": job.training_item_id,
            "training_batch_id": job.training_batch_id,
            "knowledge_base_id": job.knowledge_base_id,
            "created_by": job.created_by,
            "source_type": metadata.get("input_type") or metadata.get("source_type") or "text",
            "title": metadata.get("title") or job.training_item_id,
        }


__all__ = ["ChunkReaderAdapter", "UnderstandingJobReaderAdapter"]
