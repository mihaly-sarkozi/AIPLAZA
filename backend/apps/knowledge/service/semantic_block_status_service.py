from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.knowledge.errors import KnowledgeSourceNotFound, KnowledgeValidationError
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality


class SemanticBlockStatusService:
    _ALLOWED_STATUSES = {"draft", "approved", "rejected", "withdrawn", "outdated", "disputed"}

    def __init__(self, *, interpretation_run_store: Any) -> None:
        self._interpretation_run_store = interpretation_run_store

    def update_status(
        self,
        *,
        corpus_uuid: str,
        block_id: str,
        status: str,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in self._ALLOWED_STATUSES:
            raise KnowledgeValidationError(f"Invalid semantic block status: {status}")
        if self._interpretation_run_store is None:
            raise KnowledgeValidationError("Interpretation run store is not available.")
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            raise KnowledgeValidationError("Interpretation run listing is not available.")
        for run in list_for_corpus(corpus_uuid, limit=50):
            result = self._update_run_block(
                run=run,
                block_id=block_id,
                normalized_status=normalized_status,
                updated_by=updated_by,
            )
            if result is not None:
                return result
        raise KnowledgeSourceNotFound(f"Semantic block not found: {block_id}")

    def _update_run_block(
        self,
        *,
        run: Any,
        block_id: str,
        normalized_status: str,
        updated_by: int | None,
    ) -> dict[str, Any] | None:
        metadata = dict(run.metadata or {})
        blocks = list(metadata.get("semantic_blocks") or [])
        changed = False
        updated_block: dict[str, Any] | None = None
        next_blocks: list[Any] = []
        for block in blocks:
            if not isinstance(block, dict) or str(block.get("id") or "") != str(block_id):
                next_blocks.append(block)
                continue
            updated_block = dict(block)
            block_metadata = dict(updated_block.get("metadata") or {})
            block_metadata["block_status"] = normalized_status
            block_metadata["status_updated_by"] = updated_by
            block_metadata["status_updated_at"] = _utcnow().isoformat()
            updated_block["metadata"] = block_metadata
            updated_block["block_status"] = normalized_status
            changed = True
            next_blocks.append(updated_block)
        if not changed:
            return None
        refreshed_blocks = enrich_semantic_blocks_with_quality(
            [dict(item) for item in next_blocks if isinstance(item, dict)],
            existing_blocks=[],
            source_type=None,
        )
        refreshed_by_id = {str(item.get("id") or ""): item for item in refreshed_blocks}
        metadata["semantic_blocks"] = [
            refreshed_by_id.get(str(item.get("id") or ""), item) if isinstance(item, dict) else item
            for item in next_blocks
        ]
        self._interpretation_run_store.update(replace(run, metadata=metadata, updated_at=_utcnow()))
        return {
            "block_id": block_id,
            "status": normalized_status,
            "interpretation_run_id": run.id,
            "block": refreshed_by_id.get(str(block_id), updated_block or {}),
        }


__all__ = ["SemanticBlockStatusService"]
