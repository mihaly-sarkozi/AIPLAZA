from __future__ import annotations

# backend/apps/kb/kb_training/storage/TrainingRawRefBuilder.py
# Feladat: Tanítási nyers anyag object storage kulcsok építése.
# Sárközi Mihály - 2026.06.07

import re

from apps.kb.kb_training.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_training.errors.TrainingProcessingError import TrainingProcessingError

_UNSAFE_REF_SEGMENT = re.compile(r"[/\\]+")


def _safe_segment(value: str) -> str:
    segment = str(value or "").strip()
    if not segment:
        raise TrainingProcessingError(TrainingErrorCode.RAW_REF_SEGMENT_EMPTY)
    cleaned = _UNSAFE_REF_SEGMENT.sub("_", segment)
    if cleaned in {".", ".."}:
        raise TrainingProcessingError(TrainingErrorCode.RAW_REF_SEGMENT_INVALID)
    return cleaned


def build_text_raw_ref(
    *,
    tenant: str,
    knowledge_base_id: str,
    training_batch_id: str,
    training_item_id: str,
) -> str:
    tenant_slug = _safe_segment(tenant or "default")
    kb_id = _safe_segment(knowledge_base_id)
    batch_id = _safe_segment(training_batch_id)
    item_id = _safe_segment(training_item_id)
    return f"tenants/{tenant_slug}/kb/{kb_id}/training/{batch_id}/{item_id}/input.txt"


__all__ = ["build_text_raw_ref"]
