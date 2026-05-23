# backend/apps/knowledge/api/router.py
# Feladat: A knowledge app HTTP API routere, amely a forrás, ingest, query, index és admin jellegű endpointokat komponálja. A feltöltésbiztonsági és háttérjob helper logikák külön support modulokba kerültek, itt a kompatibilis route export marad. Program-specifikus knowledge API belépési pont.
# Sárközi Mihály - 2026.05.21

import logging
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse

from apps.knowledge.api.background_jobs import (
    enqueue_index_build_job as _enqueue_index_build_job,
    enqueue_ingest_item_reprocess_job as _enqueue_ingest_item_reprocess_job,
    process_ingest_run_and_start_index as process_ingest_run_and_start_index,
)
from apps.knowledge.application import IngestQueueUnavailableError, KnowledgeIngestApplicationService
from apps.knowledge.api.file_ingest_use_cases import FileIngestEstimateCommand, FileIngestRunCommand, FileIngestUseCase
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
from apps.knowledge.api.upload_support import (
    assert_file_count as _assert_file_count,
    assert_total_storage_limit as _assert_total_storage_limit,
    assert_training_char_limit as _assert_training_char_limit,
    ensure_training_mfa as _ensure_training_mfa,
    ensure_training_quota as _ensure_training_quota,
    guard_pdf_limits as _guard_pdf_limits,
    read_upload_limited as _read_upload_limited,
    record_training_usage as _record_training_usage,
    resolve_ingest_upload_policy as _resolve_ingest_upload_policy,
    scan_upload_or_raise as _scan_upload_or_raise,
    stream_upload_to_spooled_file as _stream_upload_to_spooled_file,
    training_quota_status as _training_quota_status,
    validate_upload_magic_type as _validate_upload_magic_type,
    validate_upload_type as _validate_upload_type,
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
from apps.knowledge.router.knowledge_router import router as knowledge_management_router
from core.kernel.config.config_loader import get_app_env, settings
from core.kernel.config.environment import is_production_env
from core.kernel.http.security_errors import security_http_exception
from core.kernel.security.rate_limit import limiter

router = APIRouter()
router.include_router(knowledge_management_router)
logger = logging.getLogger(__name__)


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


@router.post("/knowledge/corpora/{corpus_uuid}/sources/file", response_model=SourceResponse, deprecated=True)
@limiter.limit("5/minute")
async def create_file_source(
    request: Request,
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    file: UploadFile = File(...),
):
    raise HTTPException(
        status_code=410,
        detail=(
            "A direkt file source endpoint le van tiltva, mert szinkron parser munkát futtatna. "
            "Használd a /knowledge/corpora/{corpus_uuid}/ingest/files endpointot."
        ),
    )


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/text", response_model=IngestRunResponse)
@limiter.limit("10/minute")
def create_text_ingest_run(
    request: Request,
    corpus_uuid: str,
    body: IngestCreateTextRequest,
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
    try:
        run = KnowledgeIngestApplicationService(facade).create_text_run_and_enqueue(
            tenant_slug=tenant.slug or None,
            corpus_uuid=corpus_uuid,
            title=body.title,
            text=body.text,
            created_by=current_user.id,
        )
    except IngestQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _record_training_usage(tenant, char_count=text_char_count, storage_bytes=text_storage_bytes)
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
    return await FileIngestUseCase().estimate(FileIngestEstimateCommand(tenant=tenant, files=files))


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/files", response_model=IngestRunResponse)
@limiter.limit("3/minute")
async def create_file_ingest_run(
    request: Request,
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    files: list[UploadFile] = File(...),
    character_counts: list[int] = Form(default=[]),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    try:
        run = await FileIngestUseCase().create_run_and_enqueue(
            FileIngestRunCommand(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                files=files,
                character_counts=character_counts,
                created_by=current_user.id,
            ),
            ingest_service=KnowledgeIngestApplicationService(facade),
        )
        return build_ingest_run_response(
            run,
            items=facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id)),
            events=facade.list_ingest_events(run.id),
            created_by_label=facade.user_label(current_user.id),
        )
    except IngestQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/urls", response_model=IngestRunResponse)
@limiter.limit("3/minute")
def create_url_ingest_run(
    request: Request,
    corpus_uuid: str,
    body: IngestCreateUrlRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if is_production_env(get_app_env()) and not bool(getattr(settings, "knowledge_url_ingest_enabled", False)):
        raise HTTPException(status_code=503, detail="URL ingest ideiglenesen letiltva biztonsági okból.")
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    _ensure_training_mfa(current_user)
    try:
        run = KnowledgeIngestApplicationService(facade).create_url_run_and_enqueue(
            tenant_slug=tenant.slug or None,
            corpus_uuid=corpus_uuid,
            urls=[item.model_dump(mode="json") for item in body.items],
            created_by=current_user.id,
        )
    except IngestQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return build_ingest_run_response(
        run,
        items=facade.enrich_ingest_items_with_document_metrics(facade.list_ingest_items(run.id)),
        events=facade.list_ingest_events(run.id),
        created_by_label=facade.user_label(current_user.id),
    )


@router.get("/knowledge/corpora/{corpus_uuid}/ingest/runs", response_model=IngestRunListResponse)
def list_ingest_runs(
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
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
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    run = facade.get_ingest_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    can_view_ingest_run = getattr(facade, "can_view_ingest_run", None)
    if callable(can_view_ingest_run):
        allowed = bool(can_view_ingest_run(current_user, run))
    else:
        allowed = bool(
            facade.user_can_use(run.corpus_uuid, current_user.id, current_user)
            or facade.user_can_train(run.corpus_uuid, current_user.id, current_user)
        )
    if not allowed:
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
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
    if not facade.can_view_ingest_run(current_user, run):
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
    if not facade.can_view_ingest_item(current_user, item):
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
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    item = facade.get_ingest_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ingest item not found")
    if not facade.can_reprocess_ingest_item(current_user, item):
        raise HTTPException(status_code=403, detail="No permission to reprocess this ingest item")
    _ensure_training_mfa(current_user)
    try:
        run = facade.request_ingest_item_reprocess(item_id, current_user_id=current_user.id)
        _enqueue_ingest_item_reprocess_job(
            tenant_slug=tenant.slug or None,
            item_id=item_id,
            current_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    kb = facade.get(body.corpus_uuid)
    if not facade.can_start_index_build(current_user, kb):
        raise HTTPException(status_code=403, detail="No permission to build this corpus")
    _ensure_training_mfa(current_user)
    build = facade.schedule_index_build(
        tenant=tenant.slug or "",
        corpus_uuid=body.corpus_uuid,
        index_profile_key=body.index_profile_key,
        created_by=current_user.id,
    )
    try:
        _enqueue_index_build_job(tenant_slug=tenant.slug or None, build_id=build.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return build_index_build_response(build)


@router.get("/knowledge/index-builds/{build_id}", response_model=IndexBuildResponse)
def get_index_build(
    build_id: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
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
        raise security_http_exception()
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
        raise security_http_exception()
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
    if not facade.can_view_knowledge_metrics(current_user):
        raise security_http_exception()
    return facade.get_metrics()


__all__ = ["router"]
