from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile
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
    MentionResponse,
    MetricsResponse,
    ParagraphResponse,
    QueryRunResponse,
    RetrievalProfilePayload,
    RetrievalRequest,
    SentenceInterpretationDetailResponse,
    SentenceResponse,
    SourceCreateTextRequest,
    SourceResponse,
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
from core.di import run_with_tenant_schema
from shared.documents.text_extraction import extract_text_from_upload

router = APIRouter()
router.include_router(legacy_router)


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
    background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_run, run.id)
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
    background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_run, run.id)
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
    background_tasks.add_task(run_with_tenant_schema, tenant.slug or None, facade.process_ingest_run, run.id)
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
):
    run = facade.get_ingest_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    if not facade.user_can_train(run.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
    trace = facade.get_ingest_run_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Ingest run trace not found")
    return trace


@router.get("/knowledge/dev/latest-trace", response_model=IngestRunTraceResponse)
def get_latest_ingest_run_trace(
    tenant: KnowledgeTenantDep,
    facade: KnowledgeFacadeDep,
    current_user: CurrentKnowledgeUserDep,
):
    trace = facade.get_latest_ingest_run_trace()
    if trace is None:
        raise HTTPException(status_code=404, detail="No ingest run trace found")
    run = facade.get_ingest_run(trace["run_id"])
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    if not facade.user_can_train(run.corpus_uuid, current_user.id, current_user):
        raise HTTPException(status_code=403, detail="No permission to view this ingest run")
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
    return build_query_run_response(run)


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
    return packet


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
