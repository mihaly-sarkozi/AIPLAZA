import asyncio
import concurrent.futures
from html import unescape
import io
import logging
import re
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse

from apps.knowledge.api.schemas import (
    ChatContextResponse,
    ClaimResponse,
    ContextProfilePayload,
    IngestRunTraceResponse,
    IngestCreateTextRequest,
    IngestCreateUrlRequest,
    IngestFileEstimateResponse,
    IngestRunListResponse,
    IngestRunResponse,
    IndexBuildCreateRequest,
    IndexBuildResponse,
    KnowledgeFeedbackRequest,
    KnowledgeFeedbackResponse,
    KnowledgeQualityReportResponse,
    LineageResponse,
    MentionResponse,
    MetricsResponse,
    ParagraphResponse,
    QueryRunResponse,
    RetrievalProfilePayload,
    RetrievalRequest,
    SentenceInterpretationDetailResponse,
    SentenceResponse,
    SemanticBlockStatusRequest,
    SemanticBlockStatusResponse,
    SourceContentResponse,
    SourceCreateTextRequest,
    SourceResponse,
    SourceWithdrawalRequest,
    SourceWithdrawalResponse,
)
from apps.knowledge.dependencies import CurrentKnowledgeUserDep, KnowledgeFacadeDep, KnowledgeTenantDep
from apps.knowledge.domain.context_profile import ContextProfile
from apps.knowledge.domain.retrieval_profile import RetrievalProfile
from apps.knowledge.mappers.knowledge_mapper import (
    build_claim_response,
    build_ingest_run_response,
    build_index_build_response,
    build_mention_response,
    build_paragraph_response,
    build_query_run_response,
    build_sentence_response,
    build_sentence_interpretation_response,
    build_source_response,
)
from apps.knowledge.router.knowledge_router import router as legacy_router
from apps.knowledge.ingest_jobs import process_ingest_run_and_start_index_async
from apps.contracts.service_keys import MODULE_KNOWLEDGE_EVENT_CHANNEL
from apps.di import get_service as get_module_service
from core.di import get_login_service, get_service, run_async_with_tenant_schema, run_with_tenant_schema
from core.kernel.config import app_settings
from core.kernel.config.environment import get_app_env
from core.kernel.security.rate_limit import limiter
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from shared.documents.text_extraction import extract_text_from_upload

router = APIRouter()
router.include_router(legacy_router)
logger = logging.getLogger(__name__)
_RECOVERY_SWEEP_LOCK = threading.Lock()
_RECOVERY_SWEEP_LAST_TS = 0.0
_RECOVERY_SWEEP_MIN_INTERVAL_SEC = 20.0
_INDEX_WORKER_CONCURRENCY = max(1, int(getattr(app_settings, "embedding_worker_concurrency", 2) or 2))
_INDEX_WORKER_SEMAPHORE = threading.Semaphore(_INDEX_WORKER_CONCURRENCY)
_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
_PARSER_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)
_DEFAULT_ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
_GENERIC_ALLOWED_MIME = {"application/octet-stream"}
_ALLOWED_MIME_BY_EXT: dict[str, set[str]] = {
    ".txt": {"text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
}


class _UploadSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class IngestUploadPolicy:
    profile: str
    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    max_training_chars: int | None


def _tenant_plan_code(tenant: Any) -> str:
    config = getattr(tenant, "config", None)
    package = str(getattr(config, "package", "") or "").strip().lower()
    if package:
        return package
    return "free"


def _is_demo_tenant(tenant: Any) -> bool:
    flags = getattr(getattr(tenant, "config", None), "feature_flags", None) or {}
    return bool(flags.get("demo_mode"))


def _resolve_ingest_upload_policy(tenant: Any) -> IngestUploadPolicy:
    # Launch hardening profiles
    if _is_demo_tenant(tenant):
        return IngestUploadPolicy(
            profile="demo",
            max_files=3,
            max_file_bytes=5 * 1024 * 1024,
            max_total_bytes=15 * 1024 * 1024,
            max_training_chars=100_000,
        )
    plan = _tenant_plan_code(tenant)
    if plan == "starter":
        return IngestUploadPolicy(
            profile="starter",
            max_files=10,
            max_file_bytes=10 * 1024 * 1024,
            max_total_bytes=50 * 1024 * 1024,
            max_training_chars=None,
        )
    # growth/pro/business/enterprise/default
    return IngestUploadPolicy(
        profile="pro",
        max_files=20,
        max_file_bytes=25 * 1024 * 1024,
        max_total_bytes=250 * 1024 * 1024,
        max_training_chars=None,
    )


def _extension_from_filename(filename: str) -> str:
    name = str(filename or "").strip().lower()
    if "." not in name:
        return ""
    return f".{name.rsplit('.', 1)[1]}"


def _validate_upload_type(filename: str, mime_type: str | None) -> None:
    ext = _extension_from_filename(filename)
    if ext not in _DEFAULT_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file extension. Allowed: .txt, .pdf, .docx")
    normalized_mime = str(mime_type or "").strip().lower()
    if not normalized_mime:
        return
    allowed_for_ext = _ALLOWED_MIME_BY_EXT.get(ext, set())
    if normalized_mime in allowed_for_ext or normalized_mime in _GENERIC_ALLOWED_MIME:
        return
    raise HTTPException(status_code=415, detail=f"MIME type '{normalized_mime}' is not allowed for '{ext}'")


def _sniff_magic_type(raw: bytes) -> str:
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06") or raw.startswith(b"PK\x07\x08"):
        return "application/zip"
    if b"\x00" in raw[:4096]:
        return "application/octet-stream"
    try:
        raw[:8192].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def _inspect_docx_zip_or_raise(raw: bytes) -> dict[str, Any]:
    max_entries = max(1, int(getattr(app_settings, "upload_docx_max_zip_entries", 5000) or 5000))
    max_decompressed = max(1, int(getattr(app_settings, "upload_docx_max_decompressed_bytes", 30 * 1024 * 1024) or (30 * 1024 * 1024)))
    max_ratio = float(getattr(app_settings, "upload_docx_max_compression_ratio", 120.0) or 120.0)
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > max_entries:
                raise _UploadSecurityError("DOCX archive too complex (too many entries).")
            total_uncompressed = 0
            total_compressed = 0
            has_word_document = False
            has_content_types = False
            for info in infos:
                total_uncompressed += int(info.file_size or 0)
                total_compressed += int(info.compress_size or 0)
                filename = str(info.filename or "")
                if filename == "[Content_Types].xml":
                    has_content_types = True
                if filename == "word/document.xml":
                    has_word_document = True
                if total_uncompressed > max_decompressed:
                    raise _UploadSecurityError("DOCX uncompressed size exceeds allowed limit.")
            compressed_baseline = max(1, total_compressed)
            ratio = float(total_uncompressed) / float(compressed_baseline)
            if ratio > max_ratio:
                raise _UploadSecurityError("DOCX compression ratio is suspiciously high.")
            if not (has_word_document and has_content_types):
                raise _UploadSecurityError("DOCX archive structure invalid.")
            return {
                "entries": len(infos),
                "total_uncompressed": total_uncompressed,
                "total_compressed": total_compressed,
                "ratio": ratio,
            }
    except BadZipFile as exc:
        raise _UploadSecurityError("Invalid DOCX archive.") from exc


def _validate_upload_magic_type(filename: str, raw: bytes) -> None:
    if not bool(getattr(app_settings, "upload_magic_sniff_enabled", True)):
        return
    ext = _extension_from_filename(filename)
    magic_type = _sniff_magic_type(raw)
    if ext == ".pdf" and magic_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Uploaded file content does not match PDF format.")
    if ext == ".txt" and magic_type not in {"text/plain"}:
        raise HTTPException(status_code=415, detail="Uploaded file content does not match text format.")
    if ext == ".docx":
        if magic_type != "application/zip":
            raise HTTPException(status_code=415, detail="Uploaded file content does not match DOCX format.")
        try:
            _inspect_docx_zip_or_raise(raw)
        except _UploadSecurityError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc


def _pdf_page_count_heuristic(raw: bytes) -> int:
    # Fast, conservative heuristic before parser invocation.
    return max(0, int(raw.count(b"/Type /Page")))


def _guard_pdf_limits(filename: str, raw: bytes) -> None:
    if not (filename or "").lower().endswith(".pdf"):
        return
    max_pages = max(1, int(getattr(app_settings, "upload_pdf_max_pages", 200) or 200))
    estimated_pages = _pdf_page_count_heuristic(raw)
    if estimated_pages > max_pages:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large: page count exceeds limit ({max_pages}).",
        )


def _scan_with_clamav(raw: bytes) -> tuple[bool, str]:
    socket_path = str(getattr(app_settings, "upload_clamav_unix_socket_path", "") or "").strip()
    if not socket_path:
        raise RuntimeError("ClamAV socket path is missing.")
    timeout_sec = max(1, int(getattr(app_settings, "upload_malware_scan_timeout_sec", 5) or 5))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    try:
        sock.connect(socket_path)
        sock.sendall(b"zINSTREAM\x00")
        chunk_size = 1024 * 64
        for offset in range(0, len(raw), chunk_size):
            chunk = raw[offset : offset + chunk_size]
            sock.sendall(struct.pack(">I", len(chunk)))
            sock.sendall(chunk)
        sock.sendall(struct.pack(">I", 0))
        response = sock.recv(4096).decode("utf-8", errors="replace")
    finally:
        try:
            sock.close()
        except Exception:
            pass
    normalized = response.strip()
    if "FOUND" in normalized:
        return False, normalized
    if "OK" in normalized:
        return True, normalized
    raise RuntimeError(f"Unexpected ClamAV response: {normalized}")


def _scan_upload_or_raise(*, filename: str, raw: bytes) -> None:
    provider = str(getattr(app_settings, "upload_malware_scan_provider", "none") or "none").strip().lower()
    required_prod = bool(getattr(app_settings, "upload_malware_scan_required_in_prod", True))
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if provider == "none":
        if env == "prod" and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.")
        return
    if provider != "clamav":
        raise HTTPException(status_code=503, detail="Unsupported malware scan provider.")
    try:
        clean, engine_message = _scan_with_clamav(raw)
    except Exception:
        if env == "prod" and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.")
        logger.warning("Malware scan failed, continuing in non-prod mode.")
        return
    if not clean:
        logger.warning("Upload rejected by malware scanner.", extra={"filename": filename, "engine": engine_message})
        raise HTTPException(status_code=415, detail="Upload rejected by malware scan policy.")


def _extract_text_with_timeout(filename: str, raw: bytes) -> str:
    timeout_sec = max(1, int(getattr(app_settings, "upload_parser_timeout_sec", 20) or 20))
    future = _PARSER_EXECUTOR.submit(extract_text_from_upload, filename, raw)
    try:
        return str(future.result(timeout=timeout_sec) or "")
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise HTTPException(status_code=408, detail="Document parser timeout.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _read_upload_limited(upload: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes // (1024 * 1024)} MB).")
        chunks.append(chunk)
    return b"".join(chunks)


def _assert_file_count(files: list[UploadFile], *, policy: IngestUploadPolicy) -> None:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > policy.max_files:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files in one upload for '{policy.profile}' plan. Max: {policy.max_files}.",
        )


def _assert_total_storage_limit(total_bytes: int, *, policy: IngestUploadPolicy) -> None:
    if total_bytes > policy.max_total_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Total upload size exceeds limit for '{policy.profile}' plan ({policy.max_total_bytes // (1024 * 1024)} MB).",
        )


def _assert_training_char_limit(total_chars: int, *, policy: IngestUploadPolicy) -> None:
    if policy.max_training_chars is None:
        return
    if total_chars > policy.max_training_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Estimated training text too large for '{policy.profile}' plan. Max: {policy.max_training_chars} characters.",
        )


def _estimate_training_chars_for_file(filename: str, raw: bytes) -> int:
    # Keep upload/start responsive: detailed extraction runs later in the ingest pipeline with progress updates.
    if not raw:
        return 0
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return len(raw.decode("utf-8", errors="replace"))
    if name.endswith(".docx"):
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                text_parts: list[str] = []
                for member in archive.namelist():
                    if not member.startswith("word/") or not member.endswith(".xml"):
                        continue
                    xml = archive.read(member).decode("utf-8", errors="ignore")
                    text_parts.extend(unescape(value) for value in re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL))
                joined = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
                if joined:
                    return len(joined)
        except (BadZipFile, KeyError, OSError, UnicodeDecodeError):
            pass
    if name.endswith(".pdf"):
        return max(1, int(round(len(raw) * 0.06)))
    return max(1, int(round(len(raw) * 0.35)))


def _count_training_chars_for_file(filename: str, raw: bytes) -> int:
    try:
        return len(_extract_text_with_timeout(filename, raw))
    except HTTPException:
        return _estimate_training_chars_for_file(filename, raw)


def _ensure_training_quota(tenant: Any, *, char_count: int) -> None:
    allowed, reason = _training_quota_status(tenant, char_count=char_count)
    if not allowed:
        raise HTTPException(status_code=402, detail=reason or "Training quota exceeded")


def _training_quota_status(tenant: Any, *, char_count: int) -> tuple[bool, str | None]:
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    allowed, reason = usage_service.can_consume_training_chars(tenant, char_count)
    return bool(allowed), reason


def _record_training_usage(tenant: Any, *, char_count: int, storage_bytes: int) -> None:
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    usage_service.record_training_ingest(
        tenant,
        char_count=max(0, int(char_count)),
        storage_bytes=max(0, int(storage_bytes)),
    )


def _ensure_training_mfa(current_user: Any) -> None:
    if not bool(getattr(app_settings, "training_mfa_required", True)):
        return
    login_service = get_login_service()
    status = login_service.authenticator_status(int(getattr(current_user, "id", 0) or 0))
    if not bool(status.get("enabled")):
        raise HTTPException(
            status_code=403,
            detail="MFA kötelező a tanítási műveletekhez. Aktiváld az authenticator MFA-t.",
        )


async def process_ingest_run_and_start_index(
    tenant_slug: str | None,
    facade: Any,
    run_id: str,
    created_by: int | None,
    tenant_for_usage: Any | None = None,
) -> None:
    await process_ingest_run_and_start_index_async(
        tenant_slug=tenant_slug,
        run_id=run_id,
        created_by=created_by,
        facade=facade,
    )


def _enqueue_ingest_pipeline_job(
    *,
    tenant_slug: str | None,
    run_id: str,
    created_by: int | None,
    background_tasks: BackgroundTasks,
    facade: Any,
) -> None:
    channel = None
    try:
        channel = get_module_service(MODULE_KNOWLEDGE_EVENT_CHANNEL)
    except Exception:
        channel = None
    if channel is not None and hasattr(channel, "publish"):
        try:
            channel.publish(
                "knowledge.ingest_pipeline",
                {
                    "tenant_slug": tenant_slug,
                    "run_id": run_id,
                    "created_by": created_by,
                },
                idempotency_key=f"knowledge.ingest_pipeline:{tenant_slug or '_'}:{run_id}",
            )
            return
        except Exception:
            logger.exception(
                "Knowledge ingest pipeline outbox enqueue failed; fallback to BackgroundTasks",
                extra={"tenant_slug": tenant_slug, "run_id": run_id},
            )
    background_tasks.add_task(process_ingest_run_and_start_index, tenant_slug, facade, run_id, created_by)


async def _run_index_build_with_retry(
    tenant_slug: str | None,
    facade: Any,
    build_id: str,
    *,
    retries: int = 1,
) -> None:
    attempts = max(1, int(retries) + 1)
    runner = getattr(facade, "run_index_build_with_retry", None)
    if not callable(runner):
        runner = getattr(facade, "run_index_build", None)
    if not callable(runner):
        raise AttributeError("Facade does not provide run_index_build_with_retry or run_index_build")
    for attempt in range(1, attempts + 1):
        try:
            await run_async_with_tenant_schema(tenant_slug, runner, build_id)
            return
        except Exception:
            if attempt >= attempts:
                logger.exception(
                    "Index build failed after retries",
                    extra={"build_id": build_id, "tenant_slug": tenant_slug, "attempts": attempts},
                )
                raise
            logger.warning(
                "Index build failed, retrying",
                extra={"build_id": build_id, "tenant_slug": tenant_slug, "attempt": attempt, "attempts": attempts},
            )


def _run_index_build_worker_task(
    tenant_slug: str | None,
    facade: Any,
    build_id: str,
) -> None:
    acquired = _INDEX_WORKER_SEMAPHORE.acquire(timeout=1)
    if not acquired:
        logger.warning(
            "Index worker semaphore acquire timeout",
            extra={"build_id": build_id, "tenant_slug": tenant_slug},
        )
        _INDEX_WORKER_SEMAPHORE.acquire()
    try:
        asyncio.run(_run_index_build_with_retry(tenant_slug, facade, build_id))
    finally:
        _INDEX_WORKER_SEMAPHORE.release()


def _recovery_sweep_due() -> bool:
    global _RECOVERY_SWEEP_LAST_TS
    now = time.monotonic()
    with _RECOVERY_SWEEP_LOCK:
        if now - _RECOVERY_SWEEP_LAST_TS < _RECOVERY_SWEEP_MIN_INTERVAL_SEC:
            return False
        _RECOVERY_SWEEP_LAST_TS = now
        return True


def _run_recovery_sweep_for_tenant(tenant_slug: str | None, facade: Any, current_user_id: int | None) -> None:
    corpus_list = facade.list_all_unfiltered()
    for corpus in corpus_list:
        corpus_uuid = str(getattr(corpus, "uuid", "") or "")
        if not corpus_uuid:
            continue
        runs = facade.list_ingest_runs(corpus_uuid, limit=50, offset=0)
        for run in runs:
            if run.status not in {"queued", "processing"}:
                continue
            items = facade.list_ingest_items(run.id)
            stale_items = [item for item in items if facade.is_ingest_item_stale_processing(item)]
            if stale_items:
                for stale_item in stale_items:
                    try:
                        facade.request_ingest_item_reprocess(stale_item.id, current_user_id=current_user_id)
                        facade.process_ingest_item(stale_item.id)
                    except Exception:
                        logger.exception(
                            "Knowledge stale ingest item recovery failed",
                            extra={"tenant_slug": tenant_slug, "run_id": run.id, "item_id": stale_item.id},
                        )
                continue
            if facade.is_ingest_run_stale(run):
                try:
                    facade.mark_ingest_run_failed_as_stale(
                        run.id,
                        reason="Ingest run stalled without progressing items.",
                    )
                except Exception:
                    logger.exception(
                        "Knowledge stale ingest run fail-safe failed",
                        extra={"tenant_slug": tenant_slug, "run_id": run.id},
                    )
        for build in facade.list_index_builds(corpus_uuid):
            if not facade.is_index_build_stale(build):
                continue
            try:
                facade.mark_index_build_failed_as_stale(
                    build.id,
                    reason="Index build stalled and was marked failed by recovery sweep.",
                )
            except Exception:
                logger.exception(
                    "Knowledge stale index build fail-safe failed",
                    extra={"tenant_slug": tenant_slug, "build_id": build.id},
                )


def _schedule_recovery_sweep(
    *,
    background_tasks: BackgroundTasks,
    tenant_slug: str | None,
    facade: Any,
    current_user_id: int | None,
) -> None:
    if not _recovery_sweep_due():
        return
    background_tasks.add_task(
        run_with_tenant_schema,
        tenant_slug,
        _run_recovery_sweep_for_tenant,
        tenant_slug,
        facade,
        current_user_id,
    )


def _query_debug_payload(*, endpoint_called: str, query_text: str, response: dict[str, Any]) -> dict[str, Any]:
    metadata = response.get("metadata") if isinstance(response.get("metadata"), dict) else {}
    matched_chunks = response.get("matched_chunks") or []
    matched_claims = response.get("matched_claims") or []
    answer_text = str(response.get("answer_text") or "")
    answer_mode = response.get("answer_mode") or "no_answer"
    conflict_marker_included = (
        bool(response.get("conflict_marker_included") or metadata.get("conflict_marker_included"))
        or answer_mode == "conflict"
        or any(bool(item.get("conflict_marker")) for item in matched_claims)
    )
    evidence = (
        response.get("evidence_summary")
        or metadata.get("evidence_summary")
        or (metadata.get("query_debug") or {}).get("evidence")
        or ((metadata.get("synthesis") or {}).get("synthesis_debug") or {}).get("evidence")
        or []
    )
    explanation = response.get("explanation") or metadata.get("explanation") or (metadata.get("query_debug") or {}).get("explanation") or {}
    payload = {
        "endpoint_called": endpoint_called,
        "query_text": query_text,
        "query_profile": response.get("query_profile") or metadata.get("query_profile") or {},
        "matched_chunks_count": len(matched_chunks),
        "matched_claims_count": len(matched_claims),
        "conflict_marker_included": conflict_marker_included,
        "temporal_context_used": bool(response.get("temporal_context_used") or metadata.get("temporal_context_used")),
        "synthesis_called": bool(metadata.get("synthesis_called") or response.get("answer_mode") is not None),
        "answer_text": answer_text,
        "answer_mode": answer_mode,
        "cited_claim_ids": response.get("cited_claim_ids") or metadata.get("cited_claim_ids") or [],
        "cited_sentence_ids": response.get("cited_sentence_ids") or metadata.get("cited_sentence_ids") or [],
        "cited_source_ids": response.get("cited_source_ids") or metadata.get("cited_source_ids") or response.get("source_ids") or metadata.get("source_ids") or [],
        "evidence": evidence,
        "explanation": explanation,
        "response_contains_answer_text": bool(answer_text),
    }
    if isinstance(metadata, dict):
        metadata["query_debug"] = payload
        response["metadata"] = metadata
    response["query_debug"] = payload
    logger.info("knowledge.query.debug", extra={"knowledge_query_debug": payload})
    return payload


def _retrieval_profile_from_payload(payload: RetrievalProfilePayload | None) -> RetrievalProfile | None:
    if payload is None:
        return None
    return RetrievalProfile(
        key=payload.key,
        top_k=payload.top_k,
        rerank=payload.rerank,
        score_threshold=payload.score_threshold,
        duplicate_collapse=payload.duplicate_collapse,
        source_grouping=payload.source_grouping,
    )


def _context_profile_from_payload(payload: ContextProfilePayload | None) -> ContextProfile | None:
    if payload is None:
        return None
    return ContextProfile(
        key=payload.key,
        max_context_chars=payload.max_context_chars,
        max_chunks=payload.max_chunks,
        deduplicate=payload.deduplicate,
        citation_limit=payload.citation_limit,
        ordering=payload.ordering,
    )


@router.get("/knowledge/corpora/{corpus_uuid}/sources", response_model=list[SourceResponse])
def list_sources(
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this corpus")
    return [build_source_response(item) for item in facade.list_sources(corpus_uuid)]


@router.get("/knowledge/sources/{source_id}/content", response_model=SourceContentResponse)
def get_source_content(
    source_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    source = facade.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not facade.user_can_use(source.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this source")
    content = facade.get_source_content(source_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return content


@router.get("/knowledge/sources/{source_id}/download")
def download_source_content(
    source_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    source = facade.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not facade.user_can_use(source.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this source")
    download = facade.get_source_download(source_id)
    if download is None:
        raise HTTPException(status_code=404, detail="Source content not found")
    filename = str(download.get("filename") or source.title or source.id)
    return Response(
        content=download.get("body") or b"",
        media_type=str(download.get("content_type") or "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/knowledge/corpora/{corpus_uuid}/sources/text", response_model=SourceResponse)
@limiter.limit("10/minute")
def create_text_source(
    request: Request,
    corpus_uuid: str,
    body: SourceCreateTextRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    source = facade.create_source(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        title=body.title,
        source_type="text",
        raw_content=body.text,
        file_ref=None,
        created_by=current_user.id,
    )
    return build_source_response(source)


@router.post("/knowledge/corpora/{corpus_uuid}/sources/file", response_model=SourceResponse)
@limiter.limit("5/minute")
async def create_file_source(
    request: Request,
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    file: UploadFile = File(...),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    policy = _resolve_ingest_upload_policy(tenant)
    _validate_upload_type(file.filename or "upload.bin", file.content_type)
    raw = await _read_upload_limited(file, max_bytes=policy.max_file_bytes)
    _validate_upload_magic_type(file.filename or "upload.bin", raw)
    _guard_pdf_limits(file.filename or "upload.bin", raw)
    _scan_upload_or_raise(filename=file.filename or "upload.bin", raw=raw)
    _assert_total_storage_limit(len(raw), policy=policy)
    try:
        text = _extract_text_with_timeout(file.filename or "upload.txt", raw).strip()
    except HTTPException:
        raise
    _assert_training_char_limit(len(text), policy=policy)
    source = facade.create_source(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        title=(file.filename or "upload")[:200],
        source_type="file",
        raw_content=text,
        file_ref=file.filename,
        created_by=current_user.id,
    )
    return build_source_response(source)


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/text", response_model=IngestRunResponse)
@limiter.limit("10/minute")
def create_text_ingest_run(
    request: Request,
    corpus_uuid: str,
    body: IngestCreateTextRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    text_char_count = len(body.text or "")
    text_storage_bytes = len((body.text or "").encode("utf-8"))
    _ensure_training_quota(tenant, char_count=text_char_count)
    run = facade.create_text_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        title=body.title,
        text=body.text,
        created_by=current_user.id,
    )
    _record_training_usage(tenant, char_count=text_char_count, storage_bytes=text_storage_bytes)
    _enqueue_ingest_pipeline_job(
        tenant_slug=tenant.slug or None,
        run_id=run.id,
        created_by=current_user.id,
        background_tasks=background_tasks,
        facade=facade,
    )
    return build_ingest_run_response(
        run,
        items=facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id)),
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(current_user.id),
    )


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/files/estimate", response_model=IngestFileEstimateResponse)
@limiter.limit("5/minute")
async def estimate_file_ingest_run(
    request: Request,
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    files: list[UploadFile] = File(...),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    policy = _resolve_ingest_upload_policy(tenant)
    _assert_file_count(files, policy=policy)
    items: list[dict[str, object]] = []
    total_char_count = 0
    total_storage_bytes = 0
    for upload in files:
        filename = upload.filename or "upload.bin"
        _validate_upload_type(filename, upload.content_type)
        raw = await _read_upload_limited(upload, max_bytes=policy.max_file_bytes)
        _validate_upload_magic_type(filename, raw)
        _guard_pdf_limits(filename, raw)
        _scan_upload_or_raise(filename=filename, raw=raw)
        char_count = _count_training_chars_for_file(filename, raw)
        storage_bytes = len(raw)
        total_char_count += char_count
        total_storage_bytes += storage_bytes
        _assert_total_storage_limit(total_storage_bytes, policy=policy)
        _assert_training_char_limit(total_char_count, policy=policy)
        items.append(
            {
                "filename": filename,
                "mime_type": upload.content_type,
                "char_count": max(0, int(char_count)),
                "storage_bytes": max(0, int(storage_bytes)),
            }
        )
    can_start, reason = _training_quota_status(tenant, char_count=total_char_count)
    return {
        "file_count": len(items),
        "total_char_count": max(0, int(total_char_count)),
        "total_storage_bytes": max(0, int(total_storage_bytes)),
        "can_start": can_start,
        "reason": reason,
        "items": items,
    }


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/files", response_model=IngestRunResponse)
@limiter.limit("3/minute")
async def create_file_ingest_run(
    request: Request,
    corpus_uuid: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    files: list[UploadFile] = File(...),
    character_counts: list[int] = Form(default=[]),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    policy = _resolve_ingest_upload_policy(tenant)
    _assert_file_count(files, policy=policy)
    file_payloads: list[dict[str, object]] = []
    total_char_count = 0
    total_storage_bytes = 0
    for index, upload in enumerate(files):
        filename = upload.filename or "upload.bin"
        _validate_upload_type(filename, upload.content_type)
        raw = await _read_upload_limited(upload, max_bytes=policy.max_file_bytes)
        _validate_upload_magic_type(filename, raw)
        _guard_pdf_limits(filename, raw)
        _scan_upload_or_raise(filename=filename, raw=raw)
        provided_char_count = int(character_counts[index]) if index < len(character_counts) else 0
        estimated_char_count = max(
            provided_char_count,
            _estimate_training_chars_for_file(filename, raw),
        )
        total_char_count += estimated_char_count
        total_storage_bytes += len(raw)
        _assert_total_storage_limit(total_storage_bytes, policy=policy)
        _assert_training_char_limit(total_char_count, policy=policy)
        file_payloads.append(
            {
                "filename": filename,
                "content": raw,
                "mime_type": upload.content_type or "application/octet-stream",
                "estimated_char_count": max(0, int(estimated_char_count)),
            }
        )
    _ensure_training_quota(tenant, char_count=total_char_count)
    run = facade.create_file_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        files=file_payloads,
        created_by=current_user.id,
    )
    _record_training_usage(tenant, char_count=0, storage_bytes=total_storage_bytes)
    _enqueue_ingest_pipeline_job(
        tenant_slug=tenant.slug or None,
        run_id=run.id,
        created_by=current_user.id,
        background_tasks=background_tasks,
        facade=facade,
    )
    return build_ingest_run_response(
        run,
        items=facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id)),
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(current_user.id),
    )


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/urls", response_model=IngestRunResponse)
@limiter.limit("3/minute")
def create_url_ingest_run(
    request: Request,
    corpus_uuid: str,
    body: IngestCreateUrlRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if get_app_env() == "prod" and not bool(getattr(app_settings, "knowledge_url_ingest_enabled", False)):
        raise HTTPException(status_code=503, detail="URL ingest ideiglenesen letiltva biztonsági okból.")
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    run = facade.create_url_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        urls=[item.model_dump() for item in body.items],
        created_by=current_user.id,
    )
    _enqueue_ingest_pipeline_job(
        tenant_slug=tenant.slug or None,
        run_id=run.id,
        created_by=current_user.id,
        background_tasks=background_tasks,
        facade=facade,
    )
    return build_ingest_run_response(
        run,
        items=facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id)),
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(current_user.id),
    )


@router.get("/knowledge/corpora/{corpus_uuid}/ingest/runs", response_model=IngestRunListResponse)
def list_ingest_runs(
    corpus_uuid: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    _schedule_recovery_sweep(
        background_tasks=background_tasks,
        tenant_slug=tenant.slug or None,
        facade=facade,
        current_user_id=current_user.id,
    )
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view ingest runs for this corpus")
    safe_limit = max(1, min(int(limit or 20), 50))
    safe_offset = max(0, int(offset or 0))
    runs = facade.list_ingest_runs(corpus_uuid, limit=safe_limit + 1, offset=safe_offset)
    page_runs = runs[:safe_limit]
    summary = facade.ingest_run_list_summary(corpus_uuid)
    response_items = []
    for run in page_runs:
        run_items = facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id))
        response_items.append(
            build_ingest_run_response(
                run,
                items=run_items,
                created_by_label=facade.user_label(run.created_by),
                item_created_by_labels={
                    item.created_by: facade.user_label(item.created_by)
                    for item in run_items
                    if item.created_by is not None
                },
            )
        )
    return {
        "items": response_items,
        "total_count": int(summary.get("total_run_count") or 0),
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": len(runs) > safe_limit,
        "summary": summary,
    }


@router.get("/knowledge/ingest/runs/{run_id}", response_model=IngestRunResponse)
def get_ingest_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    _schedule_recovery_sweep(
        background_tasks=background_tasks,
        tenant_slug=tenant.slug or None,
        facade=facade,
        current_user_id=current_user.id,
    )
    run = facade.get_ingest_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    if not facade.user_can_train(run.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
    run_items = facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id))
    stale_item = next((item for item in run_items if facade.is_ingest_item_stale_processing(item)), None)
    if stale_item is not None:
        try:
            run = facade.request_ingest_item_reprocess(stale_item.id, current_user_id=current_user.id)
            background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_item, stale_item.id)
            run_items = facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id))
        except ValueError:
            run = facade.get_ingest_run(run_id) or run
    return build_ingest_run_response(
        run,
        items=run_items,
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(run.created_by),
        item_created_by_labels={
            item.created_by: facade.user_label(item.created_by)
            for item in run_items
            if item.created_by is not None
        },
    )


@router.get("/knowledge/dev/ingest-runs/{run_id}/trace", response_model=IngestRunTraceResponse)
@limiter.limit("30/minute")
def get_ingest_run_trace(
    request: Request,
    run_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    log_level: str = Query(default="SUMMARY", pattern="^(SUMMARY|INSPECT|FULL_TRACE|summary|inspect|full_trace)$"),
    debug: bool = Query(default=False),
):
    run = facade.get_ingest_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    if not facade.user_can_train(run.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
    trace = facade.get_ingest_run_trace(run_id, log_level=log_level, debug=debug)
    if trace is None:
        raise HTTPException(status_code=404, detail="Ingest run trace not found")
    return trace


@router.get("/knowledge/ingest/items/{item_id}/raw")
@limiter.limit("30/minute")
def get_ingest_item_raw(
    request: Request,
    item_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    item = facade.get_ingest_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    if not facade.user_can_train(item.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest item")

    ingest_input = facade.get_ingest_input_for_item(item_id)
    if ingest_input is None:
        raise HTTPException(status_code=404, detail="Ingest input not found")

    if ingest_input.input_type == "text":
        filename = quote((ingest_input.metadata.get("title") if isinstance(ingest_input.metadata, dict) else None) or item.title or "training-text")
        encoding = ingest_input.encoding or "utf-8"
        return Response(
            content=(ingest_input.text_content or "").encode(encoding),
            media_type=f"text/plain; charset={encoding}",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}.txt"},
        )

    if ingest_input.input_type == "file":
        try:
            body, media_type, original_filename = facade.read_ingest_file_bytes(item_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = quote(original_filename or item.display_name or "training-file")
        return Response(
            content=body,
            media_type=media_type or "application/octet-stream",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}"},
        )

    if ingest_input.input_type == "url" and ingest_input.origin_url:
        return RedirectResponse(url=ingest_input.origin_url, status_code=307)

    raise HTTPException(status_code=400, detail="Unsupported ingest input type")


@router.post("/knowledge/ingest/items/{item_id}/reprocess", response_model=IngestRunResponse)
@limiter.limit("5/minute")
def reprocess_ingest_item(
    request: Request,
    item_id: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    item = facade.get_ingest_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    if not facade.user_can_train(item.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to reprocess this ingest item")
    _ensure_training_mfa(current_user)
    try:
        run = facade.request_ingest_item_reprocess(item_id, current_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_item, item_id)
    run_items = facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id))
    return build_ingest_run_response(
        run,
        items=run_items,
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(run.created_by),
        item_created_by_labels={
            item.created_by: facade.user_label(item.created_by)
            for item in run_items
            if item.created_by is not None
        },
    )


@router.get("/knowledge/ingest/items/{item_id}/sentences", response_model=list[SentenceResponse])
def list_ingest_item_sentences(
    item_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    item = facade.get_ingest_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    if not facade.user_can_train(item.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest item")
    return [build_sentence_response(item) for item in facade.list_sentences_for_ingest_item(item_id)]


@router.get("/knowledge/ingest/items/{item_id}/paragraphs", response_model=list[ParagraphResponse])
def list_ingest_item_paragraphs(
    item_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    item = facade.get_ingest_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    if not facade.user_can_train(item.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest item")
    return [build_paragraph_response(item) for item in facade.list_paragraphs_for_ingest_item(item_id)]


@router.get("/knowledge/sentences/{sentence_id}/interpretation", response_model=SentenceInterpretationDetailResponse)
def get_sentence_interpretation(
    sentence_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    detail = facade.get_sentence_interpretation(sentence_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Sentence interpretation not found")
    interpretation = detail["interpretation"]
    if not facade.user_can_train(interpretation.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this sentence interpretation")
    return {
        "interpretation": build_sentence_interpretation_response(interpretation),
        "mentions": [build_mention_response(item) for item in detail["mentions"]],
        "claims": [build_claim_response(item) for item in detail["claims"]],
    }


@router.post("/knowledge/index-builds", response_model=IndexBuildResponse)
@limiter.limit("2/minute")
def start_index_build(
    request: Request,
    body: IndexBuildCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(body.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to build this corpus")
    _ensure_training_mfa(current_user)
    build = facade.schedule_index_build(
        tenant=tenant.slug or "",
        corpus_uuid=body.corpus_uuid,
        index_profile_key=body.index_profile_key,
        created_by=current_user.id,
    )
    background_tasks.add_task(_run_index_build_worker_task, tenant.slug or None, facade, build.id)
    return build_index_build_response(build)


@router.get("/knowledge/index-builds/{build_id}", response_model=IndexBuildResponse)
def get_index_build(
    build_id: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    _schedule_recovery_sweep(
        background_tasks=background_tasks,
        tenant_slug=tenant.slug or None,
        facade=facade,
        current_user_id=current_user.id,
    )
    build = facade.get_index_build(build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Index build not found")
    if not facade.user_can_use(build.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this build")
    return build_index_build_response(build)


@router.post("/knowledge/retrieve", response_model=QueryRunResponse)
@limiter.limit("60/minute")
async def retrieve(
    request: Request,
    body: RetrievalRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(body.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to query this corpus")
    try:
        run = await facade.retrieve(
            tenant=tenant.slug or "",
            corpus_uuid=body.corpus_uuid,
            query=body.query,
            build_ids=body.build_ids,
            retrieval_profile=_retrieval_profile_from_payload(body.retrieval_profile),
            context_profile=_context_profile_from_payload(body.context_profile),
            compare_mode=body.compare_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = build_query_run_response(run)
    _query_debug_payload(endpoint_called="/knowledge/retrieve", query_text=body.query, response=response)
    return response


@router.post("/knowledge/chat-context", response_model=ChatContextResponse)
@limiter.limit("30/minute")
async def build_chat_context(
    request: Request,
    body: RetrievalRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(body.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to query this corpus")
    try:
        packet = await facade.build_chat_context(
            tenant=tenant.slug or "",
            corpus_uuid=body.corpus_uuid,
            query=body.query,
            build_ids=body.build_ids,
            retrieval_profile=_retrieval_profile_from_payload(body.retrieval_profile),
            context_profile=_context_profile_from_payload(body.context_profile),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _query_debug_payload(endpoint_called="/knowledge/chat-context", query_text=body.query, response=packet)
    return packet


@router.post("/knowledge/corpora/{corpus_uuid}/feedback", response_model=KnowledgeFeedbackResponse)
def apply_knowledge_feedback(
    corpus_uuid: str,
    body: KnowledgeFeedbackRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to correct this corpus")
    _ensure_training_mfa(current_user)
    try:
        return facade.apply_knowledge_feedback(
            tenant=tenant.slug or "",
            corpus_uuid=corpus_uuid,
            target_entity=body.target_entity,
            claim_text=body.claim_text,
            feedback_type=body.feedback_type,
            optional_new_claim=body.optional_new_claim,
            user_input=body.user_input,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/knowledge/corpora/{corpus_uuid}/semantic-blocks/{block_id}/status", response_model=SemanticBlockStatusResponse)
def update_semantic_block_status(
    corpus_uuid: str,
    block_id: str,
    body: SemanticBlockStatusRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to update semantic blocks in this corpus")
    _ensure_training_mfa(current_user)
    try:
        return facade.update_semantic_block_status(
            corpus_uuid=corpus_uuid,
            block_id=block_id,
            status=body.status,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge/corpora/{corpus_uuid}/sources/{source_id}/withdraw", response_model=SourceWithdrawalResponse)
def withdraw_source(
    corpus_uuid: str,
    source_id: str,
    body: SourceWithdrawalRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to withdraw sources from this corpus")
    _ensure_training_mfa(current_user)
    try:
        return facade.withdraw_source(
            tenant=tenant.slug or "",
            corpus_uuid=corpus_uuid,
            source_id=source_id,
            user_input=body.user_input,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge/corpora/{corpus_uuid}/lineage/claims/{claim_id}", response_model=LineageResponse)
def get_claim_lineage(
    corpus_uuid: str,
    claim_id: str,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this corpus")
    return facade.get_lineage(corpus_uuid=corpus_uuid, claim_id=claim_id)


@router.get("/knowledge/corpora/{corpus_uuid}/lineage/profiles/{profile_id}", response_model=LineageResponse)
def get_profile_lineage(
    corpus_uuid: str,
    profile_id: str,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this corpus")
    return facade.get_lineage(corpus_uuid=corpus_uuid, profile_id=profile_id)


@router.get("/knowledge/corpora/{corpus_uuid}/quality-report", response_model=KnowledgeQualityReportResponse)
def get_quality_report(
    corpus_uuid: str,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_use(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to access this corpus")
    return facade.get_quality_report(corpus_uuid=corpus_uuid)


@router.get("/knowledge/metrics", response_model=MetricsResponse)
def get_metrics(
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if current_user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="No permission to access knowledge metrics")
    return facade.get_metrics()


__all__ = ["router"]
