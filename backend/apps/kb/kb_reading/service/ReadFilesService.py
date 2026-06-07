from __future__ import annotations

# backend/apps/kb/kb_reading/service/ReadFilesService.py
# Feladat: Fájlok kötegelt beolvasása: ellenőrzés, tárolás, részleges siker.
# Sárközi Mihály - 2026.06.07
from datetime import datetime

from shared.utils.clock import utc_now
from typing import Any
from apps.kb.kb_reading.service.EstimateFilesService import estimate_chars_from_size
from apps.kb.kb_reading.domain.DuplicatePolicy import DEFAULT_DUPLICATE_POLICY, DuplicatePolicy
from apps.kb.kb_reading.domain.ReadEvent import ReadEvent
from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadItemStatus import ReadItemStatus
from apps.kb.kb_reading.domain.ReadRun import ReadRun
from apps.kb.kb_reading.domain.ReadRunStatus import ReadRunStatus
from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode
from apps.kb.kb_reading.domain.RetryPolicy import DEFAULT_RETRY_POLICY, RetryPolicy
from apps.kb.kb_reading.ports.ReadingEventPublisher import ReadingEventPublisher
from apps.kb.kb_reading.ports.ReadingRepository import ReadingRepository
from apps.kb.kb_reading.security.FileSniffer import FileSniffer
from apps.kb.kb_reading.security.ReadingSecurityError import ReadingSecurityError
from apps.kb.kb_reading.security.ConfigurableMalwareScanner import ConfigurableMalwareScanner
from apps.kb.kb_reading.security.MalwareScanner import MalwareScanner
from apps.kb.kb_reading.security.ReadingMalwareRejected import ReadingMalwareRejected
from apps.kb.kb_reading.security.ReadingMalwareUnavailable import ReadingMalwareUnavailable
from apps.kb.kb_reading.storage.RawWriter import RawWriter
from apps.kb.kb_reading.storage.ReadableUpload import ReadableUpload, read_upload_limited
from apps.kb.kb_reading.support import audit, metrics
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from shared.utils.hash import sha256_bytes
from shared.utils.idempotency import build_idempotency_key
from apps.kb.kb_reading.validation.ValidateFile import validate_extension, validate_file_name, validate_size
from apps.kb.kb_reading.validation.NormalizeTitle import normalize_title
from apps.kb.shared.errors import KbProcessingError, KbValidationError
from apps.kb.shared.ids import new_id
from apps.kb.kb_reading.dto.FileReadCommand import FileReadCommand
from apps.kb.kb_reading.dto.ReadFilesResult import ReadFilesResult
from apps.kb.kb_reading.service._BatchCounters import _BatchCounters
from apps.kb.kb_reading.service._PreparedFile import _PreparedFile
MALWARE_SCAN_STARTED = "malware_scan_started"
MALWARE_SCAN_COMPLETED = "malware_scan_completed"
MALWARE_SCAN_FAILED = "malware_scan_failed"
MALWARE_SCAN_REJECTED = "malware_scan_rejected"


class ReadFilesService:
    """Fájl beolvasás üzleti folyamata."""
    def __init__(
        self,
        *,
        repository: ReadingRepository,
        raw_writer: RawWriter,
        event_publisher: ReadingEventPublisher,
        config: ReadingConfig | None = None,
        duplicate_policy: DuplicatePolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        file_sniffer: FileSniffer | None = None,
        malware_scanner: MalwareScanner | None = None,
    ) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._repository = repository
        self._raw_writer = raw_writer
        self._event_publisher = event_publisher
        self._config = config or DEFAULT_READING_CONFIG
        self._duplicate_policy = duplicate_policy or DEFAULT_DUPLICATE_POLICY
        self._retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self._file_sniffer = file_sniffer or FileSniffer(config=self._config)
        self._malware_scanner = malware_scanner or ConfigurableMalwareScanner()

    async def execute(self, command: FileReadCommand) -> ReadFilesResult:
        """Végrehajtja a beolvasási folyamatot a megadott bemenettel."""
        uploads = command.uploads
        if not uploads:
            raise KbValidationError("No files provided.")
        if len(uploads) > self._config.max_files_per_batch:
            raise KbValidationError(
                f"Too many files in one upload. Max: {self._config.max_files_per_batch}.",
            )

        now = utc_now()
        run = self._create_run(
            tenant=command.tenant,
            knowledge_base_id=command.knowledge_base_id,
            created_by=command.created_by,
            batch_size=len(uploads),
            now=now,
        )

        counters = _BatchCounters()
        item_ids: list[str] = []
        batch_hashes: dict[str, str] = {}

        for upload in uploads:
            item = self._create_item(
                read_run_id=run.id,
                knowledge_base_id=command.knowledge_base_id,
            )
            item_ids.append(item.id)
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.READ_ITEM_QUEUED,
                message="File input queued for reading.",
                details={"input_type": "file"},
            )
            await self._process_upload(
                run=run,
                item=item,
                upload=upload,
                tenant=command.tenant,
                knowledge_base_id=command.knowledge_base_id,
                counters=counters,
                batch_hashes=batch_hashes,
            )

        finalized = self._finalize_run(run, counters)
        return ReadFilesResult(
            read_run_id=finalized.id,
            status=finalized.status,
            accepted_count=counters.accepted_count,
            failed_count=counters.failed_count,
            rejected_count=counters.rejected_count,
            duplicate_count=counters.duplicate_count,
            item_ids=item_ids,
        )

    async def _process_upload(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        upload: ReadableUpload,
        tenant: str,
        knowledge_base_id: str,
        counters: _BatchCounters,
        batch_hashes: dict[str, str],
    ) -> None:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        raw_filename = upload.filename or "upload.bin"
        mime_type = upload.content_type

        try:
            prepared = await self._prepare_file(
                upload=upload,
                knowledge_base_id=knowledge_base_id,
                counters=counters,
            )
        except KbValidationError as exc:
            self._reject_item(
                run=run,
                item=item,
                title=normalize_title(raw_filename, fallback=raw_filename),
                error_code=_validation_error_code(exc),
                error_message=str(exc),
                counters=counters,
                duplicate=False,
            )
            return
        except ReadingSecurityError as exc:
            self._reject_item(
                run=run,
                item=item,
                title=normalize_title(raw_filename, fallback=raw_filename),
                error_code=ReadingErrorCode.VALIDATION_ERROR,
                error_message=str(exc),
                counters=counters,
                duplicate=False,
            )
            return

        item.title = prepared.title
        item.content_hash = prepared.content_hash
        item.idempotency_key = prepared.idempotency_key
        item.metadata = {
            "filename": prepared.filename,
            "mime_type": prepared.mime_type,
            "size_bytes": len(prepared.raw),
            "estimated_char_count": prepared.estimated_char_count,
        }
        item = self._repository.update_item(item)

        duplicate_item_id = _find_duplicate_item_id(
            repository=self._repository,
            duplicate_policy=self._duplicate_policy,
            knowledge_base_id=knowledge_base_id,
            idempotency_key=prepared.idempotency_key,
            content_hash=prepared.content_hash,
            batch_hashes=batch_hashes,
            current_item_id=item.id,
        )
        if duplicate_item_id is not None:
            item.duplicate_of_item_id = duplicate_item_id
            self._reject_duplicate(run=run, item=item, counters=counters)
            return

        batch_hashes[prepared.content_hash] = item.id

        try:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=MALWARE_SCAN_STARTED,
                message="Malware scan started.",
                details={"filename": prepared.filename},
            )
            self._malware_scanner.scan_bytes_or_raise(
                filename=prepared.filename,
                raw=prepared.raw,
            )
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=MALWARE_SCAN_COMPLETED,
                message="Malware scan passed.",
                details={"filename": prepared.filename},
            )
        except ReadingMalwareRejected as exc:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=MALWARE_SCAN_REJECTED,
                message="Malware scan rejected file.",
                details={"filename": prepared.filename, "reason": str(exc)},
            )
            self._reject_item(
                run=run,
                item=item,
                title=prepared.title,
                error_code=ReadingErrorCode.UNSUPPORTED_MEDIA_TYPE,
                error_message=str(exc),
                counters=counters,
                duplicate=False,
            )
            return
        except ReadingMalwareUnavailable as exc:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=MALWARE_SCAN_FAILED,
                message="Malware scan service unavailable.",
                details={"filename": prepared.filename, "reason": str(exc)},
            )
            self._fail_item(
                run=run,
                item=item,
                error_code=ReadingErrorCode.INTERNAL_ERROR,
                error_message=str(exc),
                counters=counters,
            )
            return

        self._accept_file(
            run=run,
            item=item,
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            prepared=prepared,
            counters=counters,
        )

    async def _prepare_file(
        self,
        *,
        upload: ReadableUpload,
        knowledge_base_id: str,
        counters: _BatchCounters,
    ) -> _PreparedFile:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        raw_filename = upload.filename or "upload.bin"
        mime_type = upload.content_type
        filename = validate_file_name(raw_filename)
        validate_extension(filename, config=self._config)
        self._file_sniffer.validate_mime_type(filename, mime_type)

        raw = await read_upload_limited(upload, max_bytes=self._config.max_file_bytes)
        validate_size(len(raw), config=self._config)

        next_total = counters.total_storage_bytes + len(raw)
        if next_total > self._config.max_total_upload_bytes:
            raise KbValidationError(
                f"Total upload size exceeds limit "
                f"({self._config.max_total_upload_bytes // (1024 * 1024)} MB).",
            )
        counters.total_storage_bytes = next_total

        self._file_sniffer.validate_file_content(filename, raw)
        content_hash = sha256_bytes(raw)
        title = normalize_title(filename, fallback=filename)
        return _PreparedFile(
            filename=filename,
            mime_type=mime_type,
            raw=raw,
            content_hash=content_hash,
            idempotency_key=build_idempotency_key(
                knowledge_base_id=knowledge_base_id,
                content_hash=content_hash,
                pipeline_version=self._config.pipeline_version,
            ),
            title=title,
            estimated_char_count=estimate_chars_from_size(filename, size_bytes=len(raw)),
        )

    def _accept_file(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        tenant: str,
        knowledge_base_id: str,
        prepared: _PreparedFile,
        counters: _BatchCounters,
    ) -> None:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        item.idempotency_key = prepared.idempotency_key
        self._repository.update_item(item)

        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.STORAGE_WRITE_STARTED,
            message="Writing raw file to storage.",
            details={"input_type": "file", "filename": prepared.filename},
        )

        try:
            raw_ref = self._raw_writer.write_file(
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                read_run_id=run.id,
                read_item_id=item.id,
                data=prepared.raw,
                filename=prepared.filename,
                content_type=prepared.mime_type,
            )
        except (KbProcessingError, OSError) as exc:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.STORAGE_WRITE_FAILED,
                message="Raw file storage write failed.",
                details={"error": str(exc), "filename": prepared.filename},
            )
            self._fail_item(
                run=run,
                item=item,
                error_code=ReadingErrorCode.STORAGE_ERROR,
                error_message=str(exc),
                counters=counters,
            )
            return

        metrics.increment(metrics.METRIC_STORAGE_WRITE, input_type="file")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.STORAGE_WRITE_COMPLETED,
            message="Raw file stored successfully.",
            details={"raw_ref": raw_ref, "filename": prepared.filename},
        )
        self._event_publisher.publish_material_read(
            knowledge_base_id=knowledge_base_id,
            read_run_id=run.id,
            read_item_id=item.id,
            raw_ref=raw_ref,
            metadata={
                "input_type": "file",
                "content_hash": prepared.content_hash,
                "filename": prepared.filename,
                "title": prepared.title,
            },
        )

        item.status = ReadItemStatus.ACCEPTED
        item.raw_ref = raw_ref
        item.original_filename = prepared.filename
        item.mime_type = prepared.mime_type
        item.size_bytes = len(prepared.raw)
        item.error_code = None
        item.error_message = None
        item.retryable = False
        self._repository.update_item(item)

        counters.accepted_count += 1
        metrics.increment(metrics.METRIC_READ_ITEM_ACCEPTED, input_type="file")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_ACCEPTED,
            message="File item accepted.",
            details={"raw_ref": raw_ref},
        )

        self._event_publisher.publish_understanding_requested(
            knowledge_base_id=knowledge_base_id,
            read_run_id=run.id,
            read_item_id=item.id,
            raw_ref=raw_ref,
            metadata={
                "input_type": "file",
                "content_hash": prepared.content_hash,
                "filename": prepared.filename,
                "title": prepared.title,
            },
        )
        metrics.increment(metrics.METRIC_UNDERSTANDING_REQUESTED, input_type="file")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.UNDERSTANDING_REQUESTED,
            message="Understanding requested for accepted file item.",
            details={"raw_ref": raw_ref},
        )

    def _reject_duplicate(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        counters: _BatchCounters,
    ) -> None:
        """Elutasítja az ismétlődő tartalmat."""
        item.status = ReadItemStatus.REJECTED
        item.error_code = ReadingErrorCode.DUPLICATE_CONTENT
        item.error_message = "Duplicate file content in knowledge base."
        item.retryable = False
        self._repository.update_item(item)

        counters.rejected_count += 1
        counters.duplicate_count += 1
        metrics.increment(metrics.METRIC_DUPLICATE_DETECTED, input_type="file")
        metrics.increment(metrics.METRIC_READ_ITEM_REJECTED, reason="duplicate_content")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.DUPLICATE_DETECTED,
            message="Duplicate file content detected.",
            details={
                "content_hash": item.content_hash,
                "duplicate_of_item_id": item.duplicate_of_item_id,
            },
        )
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_REJECTED,
            message="File item rejected as duplicate content.",
            details={"error_code": ReadingErrorCode.DUPLICATE_CONTENT.value},
        )

    def _reject_item(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        title: str,
        error_code: ReadingErrorCode,
        error_message: str,
        counters: _BatchCounters,
        duplicate: bool,
    ) -> None:
        """Elutasítja az elemet és rögzíti az okot."""
        item.title = title
        item.status = ReadItemStatus.REJECTED
        item.error_code = error_code
        item.error_message = error_message
        item.retryable = False
        self._repository.update_item(item)

        counters.rejected_count += 1
        if duplicate:
            counters.duplicate_count += 1
        metrics.increment(metrics.METRIC_READ_ITEM_REJECTED, reason=error_code.value)
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_REJECTED,
            message="File item rejected.",
            details={"error_code": error_code.value, "reason": error_message},
        )

    def _fail_item(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        error_code: ReadingErrorCode,
        error_message: str,
        counters: _BatchCounters,
    ) -> None:
        """Sikertelennek jelöli az elemet újrapróbálás jelöléssel."""
        item.status = ReadItemStatus.FAILED
        item.error_code = error_code
        item.error_message = error_message
        item.retryable = self._retry_policy.is_retryable(error_code)
        self._repository.update_item(item)

        counters.failed_count += 1
        metrics.increment(metrics.METRIC_READ_ITEM_FAILED, reason=error_code.value)
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_FAILED,
            message="File item failed.",
            details={
                "error_code": error_code.value,
                "retryable": item.retryable,
                "reason": error_message,
            },
        )

    def _create_run(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        created_by: int,
        batch_size: int,
        now: datetime,
    ) -> ReadRun:
        """Létrehozza a beolvasási futást."""
        run = ReadRun(
            id=new_id("read_run"),
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            input_channel="file",
            status=ReadRunStatus.RUNNING,
            batch_size=batch_size,
            queued_count=batch_size,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=created_by,
            created_at=now,
            metadata={"input_types": ["file"], "batch_size": batch_size},
        )
        run = self._repository.create_run(run)
        metrics.increment(metrics.METRIC_READ_RUN_CREATED, input_channel="file")
        self._record_event(
            run_id=run.id,
            item_id=None,
            event_type=audit.READ_RUN_CREATED,
            message="File reading run created.",
            details={"batch_size": batch_size, "input_channel": "file"},
        )
        return run

    def _create_item(self, *, read_run_id: str, knowledge_base_id: str) -> ReadItem:
        """Létrehoz egy új elemet a futásban."""
        item = ReadItem(
            id=new_id("read_item"),
            read_run_id=read_run_id,
            knowledge_base_id=knowledge_base_id,
            input_type="file",
            title="",
            status=ReadItemStatus.PENDING,
            raw_ref=None,
            content_hash=None,
            idempotency_key=None,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
        )
        return self._repository.create_item(item)

    def _finalize_run(self, run: ReadRun, counters: _BatchCounters) -> ReadRun:
        """Lezárja a futást és frissíti az állapotot."""
        run.failed_count = counters.failed_count
        run.rejected_count = counters.rejected_count
        run.duplicate_count = counters.duplicate_count
        run.status = _resolve_run_status(
            accepted_count=counters.accepted_count,
            failed_count=counters.failed_count,
            rejected_count=counters.rejected_count,
            duplicate_count=counters.duplicate_count,
        )
        run.completed_at = utc_now()
        run.metadata = {
            **run.metadata,
            "accepted_count": counters.accepted_count,
            "total_storage_bytes": counters.total_storage_bytes,
        }
        run = self._repository.update_run(run)

        metric_name = (
            metrics.METRIC_READ_RUN_COMPLETED
            if run.status in {ReadRunStatus.COMPLETED, ReadRunStatus.PARTIAL_SUCCESS}
            else metrics.METRIC_READ_RUN_FAILED
        )
        metrics.increment(metric_name, status=run.status.value)
        self._record_event(
            run_id=run.id,
            item_id=None,
            event_type=audit.READ_RUN_COMPLETED,
            message="File reading run finished.",
            details={
                "status": run.status.value,
                "accepted_count": counters.accepted_count,
                "failed_count": counters.failed_count,
                "rejected_count": counters.rejected_count,
                "duplicate_count": counters.duplicate_count,
                "total_storage_bytes": counters.total_storage_bytes,
            },
        )
        return run

    def _record_event(
        self,
        *,
        run_id: str,
        item_id: str | None,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ReadEvent:
        """Rögzít egy eseményt az adatbázisban."""
        event = ReadEvent(
            id=new_id("read_event"),
            read_run_id=run_id,
            read_item_id=item_id,
            event_type=event_type,
            message=message,
            details=details or {},
            created_at=utc_now(),
        )
        return self._repository.create_event(event)
def _find_duplicate_item_id(
    *,
    repository: ReadingRepository,
    duplicate_policy: DuplicatePolicy,
    knowledge_base_id: str,
    idempotency_key: str,
    content_hash: str,
    batch_hashes: dict[str, str],
    current_item_id: str,
) -> str | None:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    if not duplicate_policy.reject_file_duplicate:
        return None
    if content_hash in batch_hashes:
        existing_id = batch_hashes[content_hash]
        if existing_id != current_item_id:
            return existing_id
    duplicate = repository.find_duplicate_by_idempotency_key(knowledge_base_id, idempotency_key)
    if duplicate is not None and duplicate.id != current_item_id:
        return duplicate.id
    return None
def _validation_error_code(exc: KbValidationError) -> ReadingErrorCode:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    message = str(exc).lower()
    if "mime" in message or "extension" in message or "format" in message:
        return ReadingErrorCode.UNSUPPORTED_MEDIA_TYPE
    return ReadingErrorCode.VALIDATION_ERROR
def _resolve_run_status(
    *,
    accepted_count: int,
    failed_count: int,
    rejected_count: int,
    duplicate_count: int,
) -> ReadRunStatus:
    """Meghatározza a futás végső állapotát a számlálók alapján."""
    if accepted_count > 0:
        if failed_count > 0 or rejected_count > duplicate_count:
            return ReadRunStatus.PARTIAL_SUCCESS
        return ReadRunStatus.COMPLETED
    if rejected_count > 0 and failed_count == 0 and rejected_count == duplicate_count:
        return ReadRunStatus.COMPLETED
    return ReadRunStatus.FAILED

__all__ = ["ReadFilesService"]
