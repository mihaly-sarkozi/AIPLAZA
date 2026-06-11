from __future__ import annotations

from dataclasses import dataclass

from fastapi import UploadFile

from apps.kb.kb_ingest.security.FileSniffer import FileSniffer
from apps.kb.kb_ingest.security.ReadingSecurityError import ReadingSecurityError
from apps.kb.kb_ingest.service.EstimateFilesService import estimate_chars_from_size
from apps.kb.kb_ingest.config.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.kb_ingest.validation.ValidateFile import validate_extension, validate_file_name, validate_size
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.validation.TrainingValidationError import TrainingValidationError
from apps.kb.shared.errors import KbValidationError

READ_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PreparedTrainingFile:
    filename: str
    mime_type: str | None
    raw: bytes
    char_count: int


async def prepare_training_upload(
    upload: UploadFile,
    *,
    config: ReadingConfig | None = None,
    file_sniffer: FileSniffer | None = None,
) -> PreparedTrainingFile:
    cfg = config or DEFAULT_READING_CONFIG
    sniffer = file_sniffer or FileSniffer(config=cfg)
    raw_filename = upload.filename or "upload.bin"
    mime_type = upload.content_type

    try:
        filename = validate_file_name(raw_filename)
        validate_extension(filename, config=cfg)
        sniffer.validate_mime_type(filename, mime_type)
        raw = await _read_upload_limited(upload, max_bytes=cfg.max_file_bytes)
        validate_size(len(raw), config=cfg)
        sniffer.validate_file_content(filename, raw)
    except KbValidationError as exc:
        raise TrainingValidationError(TrainingErrorCode.VALIDATION_ERROR, reason=str(exc)) from exc
    except ReadingSecurityError as exc:
        raise TrainingValidationError(TrainingErrorCode.VALIDATION_ERROR, reason=str(exc)) from exc

    size_bytes = len(raw)
    char_count = estimate_chars_from_size(filename, size_bytes=size_bytes)
    return PreparedTrainingFile(
        filename=filename,
        mime_type=mime_type,
        raw=raw,
        char_count=char_count,
    )


async def _read_upload_limited(upload: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise TrainingValidationError(
                TrainingErrorCode.VALIDATION_ERROR,
                reason=f"File too large (max {max_bytes // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise TrainingValidationError(TrainingErrorCode.VALIDATION_ERROR, reason="Uploaded file is empty.")
    return raw


__all__ = ["PreparedTrainingFile", "prepare_training_upload"]
