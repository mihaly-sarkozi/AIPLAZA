from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import RedirectResponse

from apps.knowledge.api.schemas import (
    ChatContextResponse,
    ClaimResponse,
    ContextProfilePayload,
    IngestRunTraceResponse,
    IngestCreateTextRequest,
    IngestCreateUrlRequest,
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
from core.di import run_async_with_tenant_schema, run_with_tenant_schema
from shared.documents.text_extraction import extract_text_from_upload

router = APIRouter()
router.include_router(legacy_router)
logger = logging.getLogger(__name__)


async def process_ingest_run_and_start_index(
    tenant_slug: str | None,
    facade: Any,
    run_id: str,
    created_by: int | None,
) -> None:
    try:
        completed = run_with_tenant_schema(tenant_slug, facade.process_ingest_run, run_id)
        if completed.status not in {"completed", "partial_success"} or completed.completed_count <= 0:
            return
        build = facade.schedule_index_build(
            tenant=completed.tenant,
            corpus_uuid=completed.corpus_uuid,
            index_profile_key="basic_chunk_v1",
            created_by=created_by,
        )
        await run_async_with_tenant_schema(tenant_slug, facade.run_index_build, build.id)
    except Exception:
        logger.exception("Automatic index build after ingest failed", extra={"run_id": run_id})


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
def create_text_source(
    corpus_uuid: str,
    body: SourceCreateTextRequest,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
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
async def create_file_source(
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    file: UploadFile = File(...),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    raw = await file.read()
    try:
        text = extract_text_from_upload(file.filename or "upload.txt", raw).strip()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
def create_text_ingest_run(
    corpus_uuid: str,
    body: IngestCreateTextRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    run = facade.create_text_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        title=body.title,
        text=body.text,
        created_by=current_user.id,
    )
    background_tasks.add_task(process_ingest_run_and_start_index, tenant.slug or None, facade, run.id, current_user.id)
    return build_ingest_run_response(run, items=facade.list_ingest_items(run.id), events=facade.list_ingest_events(run.id))


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/files", response_model=IngestRunResponse)
async def create_file_ingest_run(
    corpus_uuid: str,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
    files: list[UploadFile] = File(...),
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    file_payloads: list[dict[str, object]] = []
    for upload in files:
        raw = await upload.read()
        file_payloads.append(
            {
                "filename": upload.filename or "upload.bin",
                "content": raw,
                "mime_type": upload.content_type or "application/octet-stream",
            }
        )
    run = facade.create_file_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        files=file_payloads,
        created_by=current_user.id,
    )
    background_tasks.add_task(process_ingest_run_and_start_index, tenant.slug or None, facade, run.id, current_user.id)
    return build_ingest_run_response(run, items=facade.list_ingest_items(run.id), events=facade.list_ingest_events(run.id))


@router.post("/knowledge/corpora/{corpus_uuid}/ingest/urls", response_model=IngestRunResponse)
def create_url_ingest_run(
    corpus_uuid: str,
    body: IngestCreateUrlRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to train this corpus")
    run = facade.create_url_ingest_run(
        tenant=tenant.slug or "",
        corpus_uuid=corpus_uuid,
        urls=[item.model_dump() for item in body.items],
        created_by=current_user.id,
    )
    background_tasks.add_task(process_ingest_run_and_start_index, tenant.slug or None, facade, run.id, current_user.id)
    return build_ingest_run_response(run, items=facade.list_ingest_items(run.id), events=facade.list_ingest_events(run.id))


@router.get("/knowledge/corpora/{corpus_uuid}/ingest/runs", response_model=list[IngestRunResponse])
def list_ingest_runs(
    corpus_uuid: str,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view ingest runs for this corpus")
    runs = facade.list_ingest_runs(corpus_uuid)
    return [build_ingest_run_response(run, items=facade.list_ingest_items(run.id)) for run in runs]


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
    if not facade.user_can_train(run.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
    return build_ingest_run_response(run, items=facade.list_ingest_items(run.id), events=facade.list_ingest_events(run.id))


@router.get("/knowledge/dev/ingest-runs/{run_id}/trace", response_model=IngestRunTraceResponse)
def get_ingest_run_trace(
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
def get_ingest_item_raw(
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
def reprocess_ingest_item(
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
    try:
        run = facade.request_ingest_item_reprocess(item_id, current_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_item, item_id)
    return build_ingest_run_response(run, items=facade.list_ingest_items(run.id), events=facade.list_ingest_events(run.id))


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
def start_index_build(
    body: IndexBuildCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    if not facade.user_can_train(body.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to build this corpus")
    build = facade.schedule_index_build(
        tenant=tenant.slug or "",
        corpus_uuid=body.corpus_uuid,
        index_profile_key=body.index_profile_key,
        created_by=current_user.id,
    )
    background_tasks.add_task(facade.run_index_build, build.id)
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
async def retrieve(
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
async def build_chat_context(
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
