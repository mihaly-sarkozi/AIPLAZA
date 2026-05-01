from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceCreateTextRequest(BaseModel):
    title: str = Field(..., max_length=200)
    text: str = Field(..., min_length=1)


class IngestCreateTextRequest(BaseModel):
    title: str = Field(..., max_length=200)
    text: str = Field(..., min_length=1)


class IngestCreateUrlItem(BaseModel):
    url: str = Field(..., min_length=1, max_length=1024)
    title: str | None = Field(default=None, max_length=200)


class IngestCreateUrlRequest(BaseModel):
    items: list[IngestCreateUrlItem] = Field(..., min_length=1)


class IngestEventResponse(BaseModel):
    id: str
    ingest_run_id: str
    ingest_item_id: str | None = None
    event_type: str
    status: str
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class IngestItemResponse(BaseModel):
    id: str
    ingest_run_id: str
    corpus_uuid: str
    queue_order: int
    input_type: str
    display_name: str
    title: str
    origin: str | None = None
    status: str
    progress_message: str | None = None
    result_message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    duplicate_of_item_id: str | None = None
    pipeline_route: str
    content_hash: str | None = None
    source_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRunResponse(BaseModel):
    id: str
    corpus_uuid: str
    input_channel: str
    status: str
    batch_size: int
    queued_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    duplicate_count: int
    rejected_count: int
    continue_on_error: bool
    pipeline_route: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    items: list[IngestItemResponse] = Field(default_factory=list)
    events: list[IngestEventResponse] = Field(default_factory=list)


class CitationResponse(BaseModel):
    source_id: str
    build_id: str
    snippet: str
    score: float
    title: str | None = None
    chunk_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceResponse(BaseModel):
    id: str
    tenant: str
    corpus_uuid: str
    title: str
    source_type: str
    status: str
    file_ref: str | None = None
    created_by: int | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceContentResponse(BaseModel):
    id: str
    corpus_uuid: str
    title: str
    source_type: str
    file_ref: str | None = None
    original_content: str | None = None
    extracted_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentenceResponse(BaseModel):
    id: str
    source_id: str
    document_id: str
    paragraph_id: str
    order_index: int
    text_content: str
    char_start: int
    char_end: int
    token_count: int
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParagraphResponse(BaseModel):
    id: str
    source_id: str
    document_id: str
    block_id: str | None = None
    order_index: int
    text_content: str
    char_start: int
    char_end: int
    sentence_count: int
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class MentionResponse(BaseModel):
    id: str
    sentence_id: str
    mention_type: str
    text_content: str
    normalized_value: str | None = None
    char_start: int
    char_end: int
    confidence: float
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimResponse(BaseModel):
    id: str
    sentence_id: str
    subject_text: str
    predicate_text: str
    object_text: str | None = None
    claim_type: str
    assertion_mode: str
    time_mode: str
    time_label: str | None = None
    space_mode: str
    space_label: str | None = None
    confidence: float
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentenceInterpretationResponse(BaseModel):
    id: str
    sentence_id: str
    sentence_text: str
    claim_summary: str
    assertion_mode: str
    claim_type: str
    time_mode: str
    time_label: str | None = None
    space_mode: str
    space_label: str | None = None
    confidence: float
    information_value_score: float
    information_value_status: str
    information_value_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentenceInterpretationDetailResponse(BaseModel):
    interpretation: SentenceInterpretationResponse
    mentions: list[MentionResponse] = Field(default_factory=list)
    claims: list[ClaimResponse] = Field(default_factory=list)


class TraceMentionResponse(BaseModel):
    mention_id: str
    surface_text: str
    normalized_text: str
    mention_type: str
    char_start: int
    char_end: int
    confidence: float


class SpaceTimeFrameTraceResponse(BaseModel):
    frame_id: str
    time_mode: str
    time_value: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    time_precision: str | None = None
    time_confidence: float
    space_mode: str
    space_value: str | None = None
    space_precision: str | None = None
    space_confidence: float
    overall_confidence: float


class TraceClaimResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    claim_id: str
    claim_text: str
    subject_text: str
    predicate: str
    object_text: str | None = None
    claim_type: str
    claim_group: str
    claim_status: str
    confidence: float
    identity_weight: float
    similarity_weight: float
    tension_weight: float
    conflict_behavior: str
    cardinality: str
    time_mode: str = "unknown"
    space_mode: str = "unknown"
    space_time_frame: SpaceTimeFrameTraceResponse | None = None
    context_subject_applied: str | bool | None = None
    context_subject_source: str | None = None
    context_subject_source_sentence_index: int | None = None
    context_subject_source_subject: str | None = None
    context_subject_reason: str | None = None
    subject_source: str | None = None
    carryover_from_sentence_id: str | None = None
    sanitizers_applied: list[str] = Field(default_factory=list)


class TraceSentenceResponse(BaseModel):
    sentence_id: str
    order_index: int = 0
    text: str
    language: str = "unknown"
    mentions: list[TraceMentionResponse] = Field(default_factory=list)
    claims: list[TraceClaimResponse] = Field(default_factory=list)


class LocalEntityTraceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    local_entity_id: str
    canonical_name: str = ""
    canonical_key: str = ""
    entity_type: str = "unknown"
    normalized_key: str = ""
    alias_match_reason: str | None = None
    confidence: float = 0.0
    coherence_score: float = 0.0
    surface_forms: list[str] = Field(default_factory=list)
    mention_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    sentence_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)


class SubjectContextTraceSummaryResponse(BaseModel):
    context_subject_applied_count: int = 0
    context_subject_skipped_count: int = 0
    context_subject_reset_count: int = 0
    context_subject_weak_subject_override_count: int = 0


class TraceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    sentence_count: int = 0
    mention_count: int = 0
    claim_count: int = 0
    space_time_frame_count: int = 0
    semantic_block_count: int = 0
    local_entity_cluster_count: int = 0
    technical_entities: int = 0
    technical_memory_chunks: int = 0
    search_profiles: int = 0
    candidate_selection_attempted_count: int = 0
    candidate_pool_size: int = 0
    candidate_selection_count: int = 0
    candidate_group_count: int = 0
    duplicate_memory_profile_count: int = 0
    candidates_found_count: int = 0
    candidates_without_evidence_count: int = 0
    top_candidate_score: float = 0.0
    candidate_selection_ready: bool = True
    similarity_analysis_count: int = 0
    similarity_score_distribution: dict[str, Any] = Field(default_factory=dict)
    similarity_ready: bool = True
    high_similarity_count: int = 0
    medium_similarity_count: int = 0
    low_similarity_count: int = 0
    similarity_without_evidence_count: int = 0
    rejected_noise_sentence_count: int = 0
    multilingual_alias_match_count: int = 0
    candidate_duplicate_removed_count: int = 0
    similarity_duplicate_removed_count: int = 0
    canonical_entity_merge_suggestion_count: int = 0
    unknown_entity_type_examples: list[str] = Field(default_factory=list)
    bad_subject_claim_examples: list[dict[str, Any]] = Field(default_factory=list)
    tension_analysis_count: int = 0
    tension_count: int = 0
    tension_ready: bool = True
    high_tension_count: int = 0
    medium_tension_count: int = 0
    low_tension_count: int = 0
    conflict_count: int = 0
    hard_conflict_count: int = 0
    soft_conflict_count: int = 0
    contradiction_count: int = 0
    temporal_change_count: int = 0
    tension_without_evidence_count: int = 0
    decision_analysis_count: int = 0
    decision_count: int = 0
    global_profile_count: int = 0
    global_profile_update_count: int = 0
    global_profile_create_count: int = 0
    global_profile_attach_count: int = 0
    affected_profile_ids: list[str] = Field(default_factory=list)
    claim_added_count: int = 0
    claim_deduplicated_count: int = 0
    retrieval_chunk_count: int = 0
    conflicting_chunk_count: int = 0
    temporal_context_included: bool = False
    decision_ready: bool = True
    attach_existing_count: int = 0
    auto_attach_count: int = 0
    merge_required_count: int = 0
    uncertain_match_count: int = 0
    create_new_profile_count: int = 0
    create_new_count: int = 0
    keep_separate_count: int = 0
    mark_conflict_count: int = 0
    needs_review_count: int = 0
    manual_review_count: int = 0
    local_entity_count: int = 0
    low_coherence_local_entity_count: int = 0
    unknown_entity_type_count: int = 0
    entity_type_normalized_count: int = 0
    negative_claim_count: int = 0
    local_resolver_ready: bool = False
    quality: dict[str, Any] = Field(default_factory=dict)
    subject_context: SubjectContextTraceSummaryResponse = Field(default_factory=SubjectContextTraceSummaryResponse)
    context_carryover_applied_count: int = 0
    context_carryover_blocked_count: int = 0
    source_phrase_stripped_count: int = 0
    subject_suffix_normalized_count: int = 0
    carryover_missing_subject_error_count: int = 0


class IngestRunTraceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    source_id: str | None = None
    source_name: str | None = None
    language: str
    status: str
    created_at: datetime
    log_level: str = "FULL_TRACE"
    summary: TraceSummaryResponse = Field(default_factory=TraceSummaryResponse)
    top_entities: list[dict[str, Any]] = Field(default_factory=list)
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    top_problems: list[dict[str, Any]] = Field(default_factory=list)
    merge_events: list[dict[str, Any]] = Field(default_factory=list)
    inspect: dict[str, Any] = Field(default_factory=dict)
    sentences: list[TraceSentenceResponse] = Field(default_factory=list)
    local_entities: list[LocalEntityTraceResponse] = Field(default_factory=list)
    local_entity_clusters: list[dict[str, Any]] = Field(default_factory=list)
    technical_entities: list[dict[str, Any]] = Field(default_factory=list)
    technical_memory_chunks: list[dict[str, Any]] = Field(default_factory=list)
    search_profiles: list[dict[str, Any]] = Field(default_factory=list)
    semantic_blocks: list[dict[str, Any]] = Field(default_factory=list)
    candidate_selections: list[dict[str, Any]] = Field(default_factory=list)
    similarity_analyses: list[dict[str, Any]] = Field(default_factory=list)
    tension_analyses: list[dict[str, Any]] = Field(default_factory=list)
    decision_analyses: list[dict[str, Any]] = Field(default_factory=list)
    global_profiles: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_chunks: list[dict[str, Any]] = Field(default_factory=list)
    local_resolver_trace: dict[str, Any] | None = None


class IndexBuildCreateRequest(BaseModel):
    corpus_uuid: str
    index_profile_key: str = "basic_chunk_v1"


class IndexBuildResponse(BaseModel):
    id: str
    tenant: str
    corpus_uuid: str
    index_profile_key: str
    status: str
    collection_name: str
    chunk_count: int
    error: str | None = None
    created_by: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalProfilePayload(BaseModel):
    key: str = "basic_retrieval_v1"
    top_k: int = 5
    rerank: bool = False
    score_threshold: float | None = None
    duplicate_collapse: bool = True
    source_grouping: str = "source"


class ContextProfilePayload(BaseModel):
    key: str = "chat_context_v1"
    max_context_chars: int = 4000
    max_chunks: int = 6
    deduplicate: bool = True
    citation_limit: int = 6
    ordering: str = "score_desc"


class RetrievalRequest(BaseModel):
    corpus_uuid: str
    query: str = Field(..., min_length=1)
    build_ids: list[str] | None = None
    compare_mode: bool = False
    retrieval_profile: RetrievalProfilePayload | None = None
    context_profile: ContextProfilePayload | None = None


class KnowledgeFeedbackRequest(BaseModel):
    target_entity: str = Field(..., min_length=1)
    claim_text: str = Field(..., min_length=1)
    feedback_type: str = Field(..., pattern="^(correct|incorrect|replace)$")
    optional_new_claim: str | None = None
    user_input: str | None = None


class KnowledgeFeedbackResponse(BaseModel):
    feedback_event: dict[str, Any] = Field(default_factory=dict)


class SourceWithdrawalRequest(BaseModel):
    user_input: str | None = None


class SourceWithdrawalResponse(BaseModel):
    source_withdrawal_event: dict[str, Any] = Field(default_factory=dict)


class SemanticBlockStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|approved|rejected|withdrawn|outdated|disputed)$")


class SemanticBlockStatusResponse(BaseModel):
    block_id: str
    status: str
    interpretation_run_id: str
    block: dict[str, Any] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    corpus_uuid: str
    target_type: str
    target_id: str
    found: bool
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)
    builder_version: str = ""


class KnowledgeQualityReportResponse(BaseModel):
    corpus_uuid: str
    total_profiles: int = 0
    profiles_with_conflict: int = 0
    profiles_without_evidence: int = 0
    avg_claims_per_profile: float = 0.0
    metrics: dict[str, float] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    profiles: list[dict[str, Any]] = Field(default_factory=list)
    report_version: str = ""
    generated_at: str = ""
    feedback_events: list[dict[str, Any]] = Field(default_factory=list)
    source_withdrawal_events: list[dict[str, Any]] = Field(default_factory=list)


class QueryRunResponse(BaseModel):
    id: str
    tenant: str
    query: str
    corpus_uuid: str
    build_ids: list[str]
    retrieval_profile_key: str
    context_profile_key: str
    latency_ms: float
    result_count: int
    citations: list[CitationResponse]
    context_text: str
    feedback: str | None = None
    compare_mode: bool
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    query_profile: dict[str, Any] | None = None
    matched_chunks: list[dict[str, Any]] = Field(default_factory=list)
    matched_claims: list[dict[str, Any]] = Field(default_factory=list)
    filtered_out_reason: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_confidence: float = 0.0
    query_retrieval_match_count: int = 0
    query_retrieval_filtered_count: int = 0
    conflict_marker_included: bool = False
    temporal_context_used: bool = False
    answer_text: str = ""
    answer_mode: str = "no_answer"
    cited_claim_ids: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    cited_sentence_ids: list[str] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    synthesis_confidence: float = 0.0
    query_debug: dict[str, Any] = Field(default_factory=dict)


class ChatContextResponse(BaseModel):
    query_run_id: str
    context_text: str
    citations: list[CitationResponse]
    build_ids: list[str]
    retrieval_profile_key: str
    context_profile_key: str
    query_profile: dict[str, Any] | None = None
    query_detected_entities: list[dict[str, Any]] = Field(default_factory=list)
    query_intent: str | None = None
    query_filters: dict[str, Any] = Field(default_factory=dict)
    query_resolution_confidence: float = 0.0
    query_aware_retrieval: dict[str, Any] = Field(default_factory=dict)
    matched_chunks: list[dict[str, Any]] = Field(default_factory=list)
    matched_claims: list[dict[str, Any]] = Field(default_factory=list)
    filtered_out_reason: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_confidence: float = 0.0
    query_retrieval_match_count: int = 0
    query_retrieval_filtered_count: int = 0
    conflict_marker_included: bool = False
    temporal_context_used: bool = False
    answer_text: str = ""
    answer_mode: str = "no_answer"
    cited_claim_ids: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    cited_sentence_ids: list[str] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    synthesis_confidence: float = 0.0
    query_debug: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    counters: dict[str, int] = Field(default_factory=dict)
    timings: dict[str, dict[str, float | int]] = Field(default_factory=dict)


__all__ = [
    "ChatContextResponse",
    "CitationResponse",
    "ContextProfilePayload",
    "IngestCreateTextRequest",
    "IngestCreateUrlItem",
    "IngestCreateUrlRequest",
    "IngestEventResponse",
    "IngestItemResponse",
    "IngestRunResponse",
    "IndexBuildCreateRequest",
    "IndexBuildResponse",
    "KnowledgeFeedbackRequest",
    "KnowledgeFeedbackResponse",
    "KnowledgeQualityReportResponse",
    "LineageResponse",
    "MetricsResponse",
    "MentionResponse",
    "ParagraphResponse",
    "ClaimResponse",
    "QueryRunResponse",
    "RetrievalProfilePayload",
    "RetrievalRequest",
    "SourceContentResponse",
    "SourceCreateTextRequest",
    "SourceResponse",
    "SentenceResponse",
    "SentenceInterpretationDetailResponse",
    "SentenceInterpretationResponse",
    "SemanticBlockStatusRequest",
    "SemanticBlockStatusResponse",
    "SourceWithdrawalRequest",
    "SourceWithdrawalResponse",
]
