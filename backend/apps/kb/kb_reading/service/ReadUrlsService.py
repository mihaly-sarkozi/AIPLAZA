from __future__ import annotations

# backend/apps/kb/kb_reading/service/ReadUrlsService.py
# Feladat: Hálózati címek kötegelt beolvasása: letöltés, tárolás, ismétlés kezelése.
# Sárközi Mihály - 2026.06.07
from datetime import datetime

from shared.utils.clock import utc_now
from typing import Any
from urllib.parse import urlparse
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
from apps.kb.kb_reading.dto.ReadUrlItem import ReadUrlItem
from apps.kb.kb_reading.security.UrlFetcher import UrlFetchResult, UrlFetcher
from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from apps.kb.kb_reading.storage.RawWriter import RawWriter
from apps.kb.kb_reading.support import audit, metrics
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from shared.utils.hash import sha256_bytes
from shared.utils.idempotency import build_idempotency_key
from apps.kb.kb_reading.validation.NormalizeTitle import normalize_title
from apps.kb.shared.errors import KbProcessingError, KbValidationError
from apps.kb.shared.ids import new_id
from apps.kb.kb_reading.dto.UrlReadCommand import UrlReadCommand
from apps.kb.kb_reading.dto.ReadUrlsResult import ReadUrlsResult
from apps.kb.kb_reading.service._BatchCounters import _BatchCounters
from apps.kb.kb_reading.service._UrlMetadata import _UrlMetadata
class ReadUrlsService:
    """Hálózati cím beolvasás üzleti folyamata."""
    def __init__(
        self,
        *,
        repository: ReadingRepository,
        raw_writer: RawWriter,
        event_publisher: ReadingEventPublisher,
        config: ReadingConfig | None = None,
        duplicate_policy: DuplicatePolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        url_fetcher: UrlFetcher | None = None,
        fetch_timeout_sec: int = 20,
    ) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._repository = repository
        self._raw_writer = raw_writer
        self._event_publisher = event_publisher
        self._config = config or DEFAULT_READING_CONFIG
        self._duplicate_policy = duplicate_policy or DEFAULT_DUPLICATE_POLICY
        self._retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self._url_fetcher = url_fetcher or UrlFetcher(config=self._config)
        self._fetch_timeout_sec = fetch_timeout_sec

    async def execute(self, command: UrlReadCommand) -> ReadUrlsResult:
        """Végrehajtja a beolvasási folyamatot a megadott bemenettel."""
        items = command.request.items
        if not items:
            raise KbValidationError("At least one URL is required.")
        if len(items) > self._config.max_files_per_batch:
            raise KbValidationError(
                f"Too many URLs in one batch. Max: {self._config.max_files_per_batch}.",
            )

        now = utc_now()
        run = self._create_run(
            tenant=command.tenant,
            knowledge_base_id=command.knowledge_base_id,
            created_by=command.created_by,
            batch_size=len(items),
            now=now,
        )

        counters = _BatchCounters()
        item_ids: list[str] = []
        batch_hash_items: dict[str, str] = {}
        batch_item_origins: dict[str, str] = {}

        for url_item in items:
            item = self._create_item(
                read_run_id=run.id,
                knowledge_base_id=command.knowledge_base_id,
            )
            item_ids.append(item.id)
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.READ_ITEM_QUEUED,
                message="URL input queued for reading.",
                details={"input_type": "url"},
            )
            await self._process_url_item(
                run=run,
                item=item,
                url_item=url_item,
                tenant=command.tenant,
                knowledge_base_id=command.knowledge_base_id,
                counters=counters,
                batch_hash_items=batch_hash_items,
                batch_item_origins=batch_item_origins,
            )

        finalized = self._finalize_run(run, counters)
        return ReadUrlsResult(
            read_run_id=finalized.id,
            status=finalized.status,
            accepted_count=counters.accepted_count,
            failed_count=counters.failed_count,
            rejected_count=counters.rejected_count,
            duplicate_count=counters.duplicate_count,
            item_ids=item_ids,
        )

    async def _process_url_item(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        url_item: ReadUrlItem,
        tenant: str,
        knowledge_base_id: str,
        counters: _BatchCounters,
        batch_hash_items: dict[str, str],
        batch_item_origins: dict[str, str],
    ) -> None:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        origin_url = str(url_item.url).strip()
        title = normalize_title(url_item.title, fallback=origin_url)

        previous_item = self._repository.find_latest_url_item(knowledge_base_id, origin_url)
        url_meta = _UrlMetadata(
            same_url_seen_before=previous_item is not None,
            previous_item_id=previous_item.id if previous_item is not None else None,
            content_changed=True,
        )

        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.URL_FETCH_STARTED,
            message="URL fetch started.",
            details={"origin_url": origin_url},
        )

        try:
            fetched = await asyncio.to_thread(
                self._url_fetcher.fetch,
                origin_url,
                timeout=self._fetch_timeout_sec,
            )
        except ReadingUrlSecurityError as exc:
            error_code = _map_url_security_error(exc)
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.URL_FETCH_FAILED,
                message="URL fetch failed.",
                details={"origin_url": origin_url, "reason": str(exc), "code": exc.code},
            )
            if _is_retryable_url_error(error_code, self._retry_policy):
                self._fail_item(
                    run=run,
                    item=item,
                    title=title,
                    error_code=error_code,
                    error_message=str(exc),
                    counters=counters,
                )
            else:
                self._reject_item(
                    run=run,
                    item=item,
                    title=title,
                    error_code=error_code,
                    error_message=str(exc),
                    counters=counters,
                )
            return
        except Exception as exc:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.URL_FETCH_FAILED,
                message="URL fetch failed.",
                details={"origin_url": origin_url, "reason": str(exc)},
            )
            self._fail_item(
                run=run,
                item=item,
                title=title,
                error_code=ReadingErrorCode.FETCH_FAILED,
                error_message=str(exc),
                counters=counters,
            )
            return

        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.URL_FETCH_COMPLETED,
            message="URL fetch completed.",
            details={
                "origin_url": fetched.origin_url,
                "final_url": fetched.final_url,
                "status_code": fetched.status_code,
                "size_bytes": fetched.size_bytes,
            },
        )

        content_hash = sha256_bytes(fetched.body)
        url_meta = _UrlMetadata(
            same_url_seen_before=url_meta.same_url_seen_before,
            previous_item_id=url_meta.previous_item_id,
            content_changed=(
                previous_item is None or previous_item.content_hash != content_hash
            ),
        )
        idempotency_key = url_item.idempotency_key or build_idempotency_key(
            knowledge_base_id=knowledge_base_id,
            content_hash=content_hash,
            pipeline_version=self._config.pipeline_version,
        )

        item.title = title
        item.content_hash = content_hash
        item.idempotency_key = idempotency_key
        item.metadata = {
            "origin_url": fetched.origin_url,
            "final_url": fetched.final_url,
            "status_code": fetched.status_code,
            "content_type": fetched.content_type,
            "size_bytes": fetched.size_bytes,
            "same_url_seen_before": url_meta.same_url_seen_before,
            "previous_item_id": url_meta.previous_item_id,
            "content_changed": url_meta.content_changed,
        }
        item = self._repository.update_item(item)

        duplicate_of_id = _find_cross_origin_hash_duplicate(
            repository=self._repository,
            knowledge_base_id=knowledge_base_id,
            origin_url=fetched.origin_url,
            idempotency_key=idempotency_key,
            content_hash=content_hash,
            current_item_id=item.id,
            batch_hash_items=batch_hash_items,
            batch_item_origins=batch_item_origins,
        )
        if duplicate_of_id is not None:
            item.duplicate_of_item_id = duplicate_of_id
            self._reject_duplicate(run=run, item=item, counters=counters)
            return

        self._accept_url(
            run=run,
            item=item,
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            fetched=fetched,
            content_hash=content_hash,
            url_meta=url_meta,
            title=title,
            counters=counters,
            batch_hash_items=batch_hash_items,
            batch_item_origins=batch_item_origins,
        )

    def _accept_url(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        tenant: str,
        knowledge_base_id: str,
        fetched: UrlFetchResult,
        content_hash: str,
        url_meta: _UrlMetadata,
        title: str,
        counters: _BatchCounters,
        batch_hash_items: dict[str, str],
        batch_item_origins: dict[str, str],
    ) -> None:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.STORAGE_WRITE_STARTED,
            message="Writing raw URL response to storage.",
            details={"input_type": "url", "origin_url": fetched.origin_url},
        )

        try:
            raw_ref = self._raw_writer.write_url_response(
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                read_run_id=run.id,
                read_item_id=item.id,
                body=fetched.body,
                status_code=fetched.status_code,
                origin_url=fetched.origin_url,
                final_url=fetched.final_url,
                content_type=fetched.content_type,
            )
        except (KbProcessingError, OSError) as exc:
            self._record_event(
                run_id=run.id,
                item_id=item.id,
                event_type=audit.STORAGE_WRITE_FAILED,
                message="Raw URL response storage write failed.",
                details={"error": str(exc), "origin_url": fetched.origin_url},
            )
            self._fail_item(
                run=run,
                item=item,
                title=title,
                error_code=ReadingErrorCode.STORAGE_ERROR,
                error_message=str(exc),
                counters=counters,
            )
            return

        counters.total_storage_bytes += fetched.size_bytes
        metrics.increment(metrics.METRIC_STORAGE_WRITE, input_type="url")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.STORAGE_WRITE_COMPLETED,
            message="Raw URL response stored successfully.",
            details={"raw_ref": raw_ref, "origin_url": fetched.origin_url},
        )
        self._event_publisher.publish_material_read(
            knowledge_base_id=knowledge_base_id,
            read_run_id=run.id,
            read_item_id=item.id,
            raw_ref=raw_ref,
            metadata={
                "input_type": "url",
                "content_hash": content_hash,
                "origin_url": fetched.origin_url,
                "final_url": fetched.final_url,
                "title": title,
            },
        )

        item.status = ReadItemStatus.ACCEPTED
        item.raw_ref = raw_ref
        item.mime_type = fetched.content_type
        item.size_bytes = fetched.size_bytes
        item.origin_url = fetched.origin_url
        item.final_url = fetched.final_url
        item.status_code = fetched.status_code
        item.error_code = None
        item.error_message = None
        item.retryable = False
        self._repository.update_item(item)

        counters.accepted_count += 1
        metrics.increment(metrics.METRIC_READ_ITEM_ACCEPTED, input_type="url")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_ACCEPTED,
            message="URL item accepted.",
            details={"raw_ref": raw_ref},
        )

        self._event_publisher.publish_understanding_requested(
            knowledge_base_id=knowledge_base_id,
            read_run_id=run.id,
            read_item_id=item.id,
            raw_ref=raw_ref,
            metadata={
                "input_type": "url",
                "content_hash": content_hash,
                "origin_url": fetched.origin_url,
                "final_url": fetched.final_url,
                "title": title,
                "same_url_seen_before": url_meta.same_url_seen_before,
                "previous_item_id": url_meta.previous_item_id,
                "content_changed": url_meta.content_changed,
            },
        )
        metrics.increment(metrics.METRIC_UNDERSTANDING_REQUESTED, input_type="url")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.UNDERSTANDING_REQUESTED,
            message="Understanding requested for accepted URL item.",
            details={"raw_ref": raw_ref},
        )

        batch_hash_items[content_hash] = item.id
        batch_item_origins[item.id] = normalize_origin_url(fetched.origin_url)

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
        item.error_message = "Duplicate URL response content from a different origin."
        item.retryable = False
        self._repository.update_item(item)

        counters.rejected_count += 1
        counters.duplicate_count += 1
        metrics.increment(metrics.METRIC_DUPLICATE_DETECTED, input_type="url")
        metrics.increment(metrics.METRIC_READ_ITEM_REJECTED, reason="duplicate_content")
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.DUPLICATE_DETECTED,
            message="Duplicate URL body hash detected for different origin.",
            details={
                "content_hash": item.content_hash,
                "duplicate_of_item_id": item.duplicate_of_item_id,
            },
        )
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_REJECTED,
            message="URL item rejected as duplicate content.",
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
    ) -> None:
        """Elutasítja az elemet és rögzíti az okot."""
        item.title = title
        item.status = ReadItemStatus.REJECTED
        item.error_code = error_code
        item.error_message = error_message
        item.retryable = False
        self._repository.update_item(item)

        counters.rejected_count += 1
        metrics.increment(metrics.METRIC_READ_ITEM_REJECTED, reason=error_code.value)
        self._record_event(
            run_id=run.id,
            item_id=item.id,
            event_type=audit.READ_ITEM_REJECTED,
            message="URL item rejected.",
            details={"error_code": error_code.value, "reason": error_message},
        )

    def _fail_item(
        self,
        *,
        run: ReadRun,
        item: ReadItem,
        title: str,
        error_code: ReadingErrorCode,
        error_message: str,
        counters: _BatchCounters,
    ) -> None:
        """Sikertelennek jelöli az elemet újrapróbálás jelöléssel."""
        item.title = title
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
            message="URL item failed.",
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
            input_channel="url",
            status=ReadRunStatus.RUNNING,
            batch_size=batch_size,
            queued_count=batch_size,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=created_by,
            created_at=now,
            metadata={"input_types": ["url"], "batch_size": batch_size},
        )
        run = self._repository.create_run(run)
        metrics.increment(metrics.METRIC_READ_RUN_CREATED, input_channel="url")
        self._record_event(
            run_id=run.id,
            item_id=None,
            event_type=audit.READ_RUN_CREATED,
            message="URL reading run created.",
            details={"batch_size": batch_size, "input_channel": "url"},
        )
        return run

    def _create_item(self, *, read_run_id: str, knowledge_base_id: str) -> ReadItem:
        """Létrehoz egy új elemet a futásban."""
        item = ReadItem(
            id=new_id("read_item"),
            read_run_id=read_run_id,
            knowledge_base_id=knowledge_base_id,
            input_type="url",
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
            message="URL reading run finished.",
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
def normalize_origin_url(url: str) -> str:
    """Egységes formára hozza az eredeti címet."""
    parsed = urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not scheme or not host:
        return str(url or "").strip()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return f"{scheme}://{host}{path}"
def _find_cross_origin_hash_duplicate(
    *,
    repository: ReadingRepository,
    knowledge_base_id: str,
    origin_url: str,
    idempotency_key: str,
    content_hash: str,
    current_item_id: str,
    batch_hash_items: dict[str, str],
    batch_item_origins: dict[str, str],
) -> str | None:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    normalized_origin = normalize_origin_url(origin_url)

    other_item_id = batch_hash_items.get(content_hash)
    if other_item_id is not None and other_item_id != current_item_id:
        other_origin = batch_item_origins.get(other_item_id, "")
        if other_origin != normalized_origin:
            return other_item_id

    duplicate = repository.find_duplicate_by_idempotency_key(knowledge_base_id, idempotency_key)
    if duplicate is None or duplicate.id == current_item_id:
        return None

    duplicate_origin = (
        normalize_origin_url(duplicate.origin_url)
        if duplicate.origin_url
        else ""
    )
    if duplicate_origin == normalized_origin:
        return None
    return duplicate.id
def _map_url_security_error(exc: ReadingUrlSecurityError) -> ReadingErrorCode:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    code = exc.code
    if code == "DOWNLOAD_TIMEOUT":
        return ReadingErrorCode.FETCH_TIMEOUT
    if code in {
        "INVALID_SCHEME",
        "USERINFO_NOT_ALLOWED",
        "DNS_REBINDING_DETECTED",
        "REDIRECT_DOWNGRADE_BLOCKED",
    }:
        return ReadingErrorCode.INVALID_URL
    if code in {"CONTENT_TYPE_NOT_ALLOWED", "CONTENT_LENGTH_TOO_LARGE", "RESPONSE_TOO_LARGE"}:
        return ReadingErrorCode.UNSUPPORTED_MEDIA_TYPE
    if code in {
        "DNS_RESOLUTION_FAILED",
        "PRIVATE_IP_BLOCKED",
        "REDIRECT_LIMIT_EXCEEDED",
    }:
        return ReadingErrorCode.FETCH_FAILED
    return ReadingErrorCode.FETCH_FAILED
def _is_retryable_url_error(error_code: ReadingErrorCode, retry_policy: RetryPolicy) -> bool:
    """Belső segédfüggvény a folyamat egy lépéséhez."""
    return retry_policy.is_retryable(error_code)
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

__all__ = ["ReadUrlsService", "normalize_origin_url"]
