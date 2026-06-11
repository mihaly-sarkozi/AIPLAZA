from __future__ import annotations

from apps.kb.kb_ingest.dto.ReadFileEstimateResponse import ReadFileEstimateResponse
from apps.kb.kb_ingest.dto.TrainingFileEstimateItemResponse import TrainingFileEstimateItemResponse
from apps.kb.kb_ingest.dto.TrainingFileEstimateResponse import TrainingFileEstimateResponse


def to_training_file_estimate(data: ReadFileEstimateResponse) -> TrainingFileEstimateResponse:
    return TrainingFileEstimateResponse(
        file_count=data.file_count,
        total_char_count=data.total_char_count,
        total_storage_bytes=data.total_size_bytes,
        can_start=data.can_start,
        reason=data.reason,
        items=[
            TrainingFileEstimateItemResponse(
                filename=item.filename,
                mime_type=item.mime_type,
                char_count=item.char_count,
                storage_bytes=item.size_bytes,
                error_code=str(item.error_code.value) if item.error_code is not None else None,
                error_message=item.error_message,
            )
            for item in data.items
        ],
    )


__all__ = ["to_training_file_estimate"]
