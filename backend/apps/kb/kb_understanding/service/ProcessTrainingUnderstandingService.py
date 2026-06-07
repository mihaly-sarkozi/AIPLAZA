from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ProcessTrainingUnderstandingService.py
# Feladat: Egy elfogadott training item megértési feldolgozása (chunk, embed, index — későbbi lépés).
# Sárközi Mihály - 2026.06.07


class ProcessTrainingUnderstandingService:
    """Training item → kereshető tudás pipeline (jelenleg váz)."""

    def execute(
        self,
        *,
        tenant: str,
        training_item_id: str,
        training_batch_id: str,
        knowledge_base_id: str,
        raw_ref: str,
        input_type: str,
        created_by: int | None,
    ) -> None:
        _ = (
            tenant,
            training_item_id,
            training_batch_id,
            knowledge_base_id,
            raw_ref,
            input_type,
            created_by,
        )
        raise NotImplementedError("kb_understanding — training pipeline (4. lépés)")


__all__ = ["ProcessTrainingUnderstandingService"]
