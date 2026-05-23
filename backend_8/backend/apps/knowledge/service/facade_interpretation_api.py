from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class InterpretationFacadeMixin:
    def update_semantic_block_status(
        self,
        *,
        corpus_uuid: str,
        block_id: str,
        status: str,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        return self._semantic_block_status_service.update_status(
            corpus_uuid=corpus_uuid,
            block_id=block_id,
            status=status,
            updated_by=updated_by,
        )


__all__ = ["InterpretationFacadeMixin"]
