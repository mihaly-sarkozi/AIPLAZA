from __future__ import annotations

# backend/apps/kb/kb_ingest/service/EstimateFilesService.py
# Feladat: Fájl feltöltés előtti becslés: méret, típus, kvóta, indíthatóság.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11
from typing import Any

from apps.kb.kb_ingest.enums.ReadingErrorCode import ReadingErrorCode
from apps.kb.kb_ingest.ports.ReadingPolicyPort import ReadingPolicyPort
from apps.kb.kb_ingest.dto.ReadFileEstimateItemResponse import ReadFileEstimateItemResponse
from apps.kb.kb_ingest.dto.ReadFileEstimateResponse import ReadFileEstimateResponse
from apps.kb.kb_ingest.security.FileSniffer import FileSniffer
from apps.kb.kb_ingest.security.ReadingSecurityError import ReadingSecurityError
from apps.kb.kb_ingest.config.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.kb_ingest.validation.ValidateFile import validate_extension, validate_file_name, validate_size
from apps.kb.shared.errors import KbValidationError
from apps.kb.kb_ingest.dto.FileEstimateCommand import FileEstimateCommand
from apps.kb.kb_ingest.ports.ReadableUpload import ReadableUpload
READ_CHUNK_BYTES = 1024 * 1024


class EstimateFilesService:
    """Fájl becslés üzleti folyamata."""
    def __init__(
        self,
        *,
        policy: ReadingPolicyPort,
        config: ReadingConfig | None = None,
        file_sniffer: FileSniffer | None = None,
    ) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._policy = policy
        self._config = config or DEFAULT_READING_CONFIG
        self._file_sniffer = file_sniffer or FileSniffer(config=self._config)

    async def execute(self, command: FileEstimateCommand) -> ReadFileEstimateResponse:
        """Végrehajtja a beolvasási folyamatot a megadott bemenettel."""
        uploads = command.uploads
        if not uploads:
            return ReadFileEstimateResponse(
                file_count=0,
                can_start=False,
                reason="No files provided.",
            )

        if len(uploads) > self._config.max_files_per_batch:
            return ReadFileEstimateResponse(
                file_count=len(uploads),
                can_start=False,
                reason=(
                    f"Too many files in one upload. Max: {self._config.max_files_per_batch}."
                ),
            )

        items: list[ReadFileEstimateItemResponse] = []
        total_size_bytes = 0
        total_char_count = 0
        blocking_reason: str | None = None

        for upload in uploads:
            item, size_bytes, char_count = await self._estimate_upload(upload)
            items.append(item)

            if item.error_code is not None:
                if blocking_reason is None:
                    blocking_reason = item.error_message
                continue

            next_total_size = total_size_bytes + size_bytes
            if next_total_size > self._config.max_total_upload_bytes:
                overflow_message = (
                    f"Total upload size exceeds limit "
                    f"({self._config.max_total_upload_bytes // (1024 * 1024)} MB)."
                )
                items[-1] = item.model_copy(
                    update={
                        "error_code": ReadingErrorCode.VALIDATION_ERROR,
                        "error_message": overflow_message,
                    },
                )
                if blocking_reason is None:
                    blocking_reason = overflow_message
                continue

            total_size_bytes = next_total_size
            total_char_count += char_count

        quota_ok, quota_reason = _quota_status(
            self._policy,
            command.tenant,
            char_count=total_char_count,
            storage_bytes=total_size_bytes,
        )
        if not quota_ok and blocking_reason is None:
            blocking_reason = quota_reason

        has_item_errors = any(item.error_code is not None for item in items)
        can_start = not has_item_errors and quota_ok
        reason = None if can_start else (blocking_reason or quota_reason or "File estimate rejected.")

        if not quota_ok:
            items = [
                item.model_copy(update={"within_quota": False})
                if item.error_code is None
                else item
                for item in items
            ]

        return ReadFileEstimateResponse(
            file_count=len(items),
            total_size_bytes=total_size_bytes,
            total_char_count=total_char_count,
            can_start=can_start,
            reason=reason,
            is_estimate=True,
            items=items,
        )

    async def _estimate_upload(
        self,
        upload: ReadableUpload,
    ) -> tuple[ReadFileEstimateItemResponse, int, int]:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        raw_filename = upload.filename or "upload.bin"
        mime_type = upload.content_type

        try:
            filename = validate_file_name(raw_filename)
            validate_extension(filename, config=self._config)
            self._file_sniffer.validate_mime_type(filename, mime_type)
            raw = await _read_upload_limited(upload, max_bytes=self._config.max_file_bytes)
            validate_size(len(raw), config=self._config)
            self._file_sniffer.validate_file_content(filename, raw)
        except KbValidationError as exc:
            return (
                _error_item(
                    filename=raw_filename,
                    mime_type=mime_type,
                    error_code=_error_code_for_validation(exc),
                    error_message=str(exc),
                ),
                0,
                0,
            )
        except ReadingSecurityError as exc:
            return (
                _error_item(
                    filename=raw_filename,
                    mime_type=mime_type,
                    error_code=ReadingErrorCode.VALIDATION_ERROR,
                    error_message=str(exc),
                ),
                0,
                0,
            )

        size_bytes = len(raw)
        char_count = estimate_chars_from_size(filename, size_bytes=size_bytes)
        return (
            ReadFileEstimateItemResponse(
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                char_count=char_count,
                within_quota=True,
            ),
            size_bytes,
            char_count,
        )
async def _read_upload_limited(upload: ReadableUpload, *, max_bytes: int) -> bytes:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise KbValidationError(f"File too large (max {max_bytes // (1024 * 1024)} MB).")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise KbValidationError("Uploaded file is empty.")
    return raw
def estimate_chars_from_size(filename: str, *, size_bytes: int) -> int:
    """Karakterszámot becsül a fájlméret alapján."""
    if size_bytes <= 0:
        return 0
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return int(size_bytes)
    if name.endswith(".pdf"):
        return max(1, int(round(size_bytes * 0.06)))
    if name.endswith(".docx"):
        return max(1, int(round(size_bytes * 0.20)))
    return max(1, int(round(size_bytes * 0.35)))
def _quota_status(
    policy: ReadingPolicyPort,
    tenant: Any,
    *,
    char_count: int,
    storage_bytes: int,
) -> tuple[bool, str | None]:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    try:
        policy.check_training_quota(
            tenant,
            char_count=char_count,
            storage_bytes=storage_bytes,
        )
    except Exception as exc:
        message = str(exc).strip() or "Training quota exceeded."
        return False, message
    return True, None
def _error_code_for_validation(exc: KbValidationError) -> ReadingErrorCode:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    message = str(exc).lower()
    if "quota" in message:
        return ReadingErrorCode.QUOTA_EXCEEDED
    if "mime" in message or "extension" in message or "format" in message:
        return ReadingErrorCode.UNSUPPORTED_MEDIA_TYPE
    return ReadingErrorCode.VALIDATION_ERROR
def _error_item(
    *,
    filename: str,
    mime_type: str | None,
    error_code: ReadingErrorCode,
    error_message: str,
) -> ReadFileEstimateItemResponse:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    return ReadFileEstimateItemResponse(
        filename=filename,
        mime_type=mime_type,
        size_bytes=0,
        char_count=0,
        within_quota=True,
        error_code=error_code,
        error_message=error_message,
    )
__all__ = [
    "EstimateFilesService",
    "estimate_chars_from_size",
]
