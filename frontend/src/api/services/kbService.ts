/**
 * Knowledge base (tudástár) API service. Used by React Query hooks; no React dependencies.
 */
import api from "../axiosClient";

export type PersonalDataMode = "no_personal_data" | "with_confirmation" | "allowed_not_to_ai" | "no_pii_filter";
export type KnowledgeTraceLogLevel = "SUMMARY" | "INSPECT" | "FULL_TRACE";

export type KbItem = {
  uuid: string;
  name: string;
  description?: string;
  personal_data_mode: PersonalDataMode;
  /** Aktuális user taníthatja-e (backend listánál kitölti) */
  can_train?: boolean;
  /** Van-e legalább egy tanítási/ingest bejegyzés ebben az elérhető tudástárban. */
  has_training?: boolean;
  [key: string]: unknown;
};

export type KbPermissionItem = {
  user_id: number;
  email: string;
  name?: string | null;
  permission: string;
  role: "user" | "admin" | "owner";
};

export type IngestEventItem = {
  id: string;
  ingest_run_id: string;
  ingest_item_id?: string | null;
  event_type: string;
  status: string;
  message?: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type IngestItem = {
  id: string;
  ingest_run_id: string;
  corpus_uuid: string;
  queue_order: number;
  input_type: "text" | "file" | "url" | string;
  display_name: string;
  title: string;
  origin?: string | null;
  status: string;
  progress_message?: string | null;
  result_message?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  duplicate_of_item_id?: string | null;
  pipeline_route: string;
  content_hash?: string | null;
  source_id?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
  metadata: Record<string, unknown>;
};

export type SentenceItem = {
  id: string;
  source_id: string;
  document_id: string;
  paragraph_id: string;
  order_index: number;
  text_content: string;
  char_start: number;
  char_end: number;
  token_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type MentionItem = {
  id: string;
  sentence_id: string;
  mention_type: string;
  text_content: string;
  normalized_value?: string | null;
  char_start: number;
  char_end: number;
  confidence: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type ClaimItem = {
  id: string;
  sentence_id: string;
  subject_text: string;
  predicate_text: string;
  object_text?: string | null;
  context_subject_applied?: boolean | string | null;
  context_subject_source?: string | null;
  context_subject_source_sentence_index?: number | null;
  context_subject_source_subject?: string | null;
  context_subject_reason?: string | null;
  context_subject_sentence_pattern_id?: string | null;
  subject_source?: "explicit" | "carryover" | "sanitized" | string | null;
  carryover_from_sentence_id?: string | null;
  sanitizers_applied?: string[];
  claim_type: string;
  assertion_mode: string;
  time_mode: string;
  time_label?: string | null;
  space_mode: string;
  space_label?: string | null;
  confidence: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type SentenceInterpretationItem = {
  id: string;
  sentence_id: string;
  sentence_text: string;
  claim_summary: string;
  assertion_mode: string;
  claim_type: string;
  time_mode: string;
  time_label?: string | null;
  space_mode: string;
  space_label?: string | null;
  confidence: number;
  information_value_score: number;
  information_value_status: string;
  information_value_reason?: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
};

export type SentenceInterpretationDetail = {
  interpretation: SentenceInterpretationItem;
  mentions: MentionItem[];
  claims: ClaimItem[];
};

export type IngestRunTraceMention = {
  mention_id: string;
  surface_text: string;
  normalized_text: string;
  mention_type: string;
  char_start: number;
  char_end: number;
  confidence: number;
};

export type IngestRunTraceClaim = {
  claim_id: string;
  claim_text: string;
  subject_text: string;
  predicate: string;
  object_text?: string | null;
  context_subject_applied?: boolean | string | null;
  context_subject_source?: string | null;
  context_subject_source_sentence_index?: number | null;
  context_subject_source_subject?: string | null;
  context_subject_reason?: string | null;
  context_subject_sentence_pattern_id?: string | null;
  subject_source?: "explicit" | "carryover" | "sanitized" | string | null;
  carryover_from_sentence_id?: string | null;
  sanitizers_applied?: string[];
  claim_type: string;
  claim_group: string;
  claim_status: string;
  confidence: number;
  identity_weight: number;
  similarity_weight: number;
  tension_weight: number;
  conflict_behavior: string;
  cardinality: string;
  time_mode: string;
  space_mode: string;
  space_time_frame?: {
    frame_id: string;
    time_mode: string;
    time_value?: string | null;
    time_start?: string | null;
    time_end?: string | null;
    time_precision?: string | null;
    time_confidence: number;
    space_mode: string;
    space_value?: string | null;
    space_precision?: string | null;
    space_confidence: number;
    overall_confidence: number;
  } | null;
};

export type IngestRunTraceSentence = {
  sentence_id: string;
  order_index: number;
  text: string;
  language: string;
  mentions: IngestRunTraceMention[];
  claims: IngestRunTraceClaim[];
};

/** LocalResolverV1 magyarázat (grouping, típus-forrás, kohéziós faktorok). */
export type LocalEntityResolverExplanation = {
  grouping_rule?: string;
  normalized_key?: string;
  entity_type_source?: string;
  claim_count?: number;
  surface_form_count?: number;
  coherence_factors?: string[];
};

export type IngestRunTraceLocalEntity = {
  local_entity_id: string;
  canonical_name: string;
  entity_type: string;
  normalized_key: string;
  confidence: number;
  coherence_score: number;
  surface_forms: string[];
  mention_ids: string[];
  claim_ids: string[];
  sentence_ids: string[];
  evidence_refs: Record<string, unknown>[];
  explanation?: LocalEntityResolverExplanation;
};

export type IngestRunTraceTechnicalEntity = {
  technical_entity_id?: string;
  local_entity_id?: string | null;
  name?: string;
  type?: string;
  canonical_name?: string;
  entity_type?: string;
  coherence?: string;
  coherence_state?: string;
  coherence_score?: number;
  claim_groups?: Record<string, number>;
  claims?: Record<string, number>;
  time_signature?: {
    has_current_claims?: boolean;
    has_historical_claims?: boolean;
    time_values?: string[];
    dominant_time_mode?: string;
  };
  space_signature?: {
    has_bounded_space?: boolean;
    space_values?: string[];
    dominant_space_mode?: string;
  };
  relation_signature?: {
    relation_predicates?: string[];
    relation_objects?: string[];
  };
  [key: string]: unknown;
};

export type IngestRunTraceTechnicalMemoryChunk = {
  technical_memory_chunk_id?: string;
  technical_entity_id?: string | null;
  local_entity_id?: string | null;
  entity_name?: string;
  entity_type?: string;
  normalized_key?: string;
  summary_text?: string;
  facts?: Array<{
    claim_id?: string;
    sentence_id?: string;
    claim_group?: string;
    claim_type?: string;
    predicate?: string;
    object_text?: string | null;
    confidence?: number;
    time_mode?: string;
    time_value?: string | null;
    space_mode?: string;
    space_value?: string | null;
  }>;
  time_profile?: {
    dominant_time_mode?: string;
    has_current_claims?: boolean;
    has_historical_claims?: boolean;
    time_values?: string[];
  };
  space_profile?: {
    dominant_space_mode?: string;
    has_bounded_space?: boolean;
    space_values?: string[];
  };
  relation_profile?: {
    relation_predicates?: string[];
    relation_objects?: string[];
    relation_count?: number;
  };
  evidence_refs?: Record<string, unknown>[];
  coherence_state?: string;
  coherence_score?: number;
  confidence?: number;
  [key: string]: unknown;
};

export type IngestRunTraceSearchProfile = {
  search_profile_id?: string;
  technical_memory_chunk_id?: string | null;
  technical_entity_id?: string | null;
  local_entity_id?: string | null;
  entity_name?: string;
  entity_type?: string;
  normalized_key?: string;
  canonical_text?: string;
  search_text?: string;
  aliases?: string[];
  keywords?: string[];
  claim_group_signals?: Record<string, number>;
  time_filters?: {
    dominant?: string;
    values?: string[];
    has_current?: boolean;
    has_historical?: boolean;
  };
  space_filters?: {
    dominant?: string;
    values?: string[];
    has_bounded?: boolean;
  };
  relation_filters?: {
    predicates?: string[];
    objects?: string[];
  };
  evidence_refs?: Record<string, unknown>[];
  [key: string]: unknown;
};

export type IngestRunTraceCandidateSelection = {
  candidate_selection_id?: string;
  search_profile_id?: string | null;
  technical_memory_chunk_id?: string | null;
  technical_entity_id?: string | null;
  local_entity_id?: string | null;
  candidate_entity_id?: string;
  candidate_name?: string;
  candidate_type?: string;
  candidate_source?: string;
  score?: number;
  candidate_score?: number;
  reasons?: string[];
  candidate_reason?: string[];
  evidence?: {
    claim_ids?: string[];
    sentence_ids?: string[];
    source_id?: string | null;
  };
  [key: string]: unknown;
};

export type IngestRunTraceSimilarityAnalysis = {
  similarity_analysis_id?: string;
  search_profile_id?: string | null;
  technical_memory_chunk_id?: string | null;
  technical_entity_id?: string | null;
  local_entity_id?: string | null;
  candidate_entity_id?: string;
  candidate_name?: string;
  candidate_type?: string;
  total_similarity_score?: number;
  similarity_band?: "high" | "medium" | "low" | string;
  component_scores?: Record<string, number>;
  similarity_reasons?: string[];
  reasons?: string[];
  evidence?: {
    claim_ids?: string[];
    sentence_ids?: string[];
    source_id?: string | null;
    new_claim_ids?: string[];
    new_sentence_ids?: string[];
  };
  [key: string]: unknown;
};

export type IngestRunTraceTensionAnalysis = {
  tension_analysis_id?: string;
  candidate_name_a?: string;
  candidate_name_b?: string;
  tension_detected?: boolean;
  tension_score?: number;
  tension_band?: "high" | "medium" | "low" | string;
  tension_type?: string;
  tension_reason?: string;
  tension_reasons?: string[];
  conflicting_claim_ids?: string[];
  evidence?: {
    claim_ids?: string[];
    sentence_ids?: string[];
    profile_id?: string | null;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type IngestRunTraceRetrievalChunk = {
  profile_id?: string | null;
  entity_name?: string;
  canonical_key?: string;
  retrieval_chunk_text?: string;
  structured_facts?: {
    active?: Record<string, unknown>[];
    conflicts?: Record<string, unknown>[];
    historical?: Record<string, unknown>[];
    tension_types?: string[];
    [key: string]: unknown;
  };
  evidence_ids?: string[];
  confidence?: number;
  conflicting?: boolean;
  temporal_context_included?: boolean;
  builder_version?: string;
  [key: string]: unknown;
};

export type IngestRunTraceSemanticBlock = {
  id?: string;
  source_id?: string;
  document_id?: string;
  paragraph_ids?: string[];
  sentence_ids?: string[];
  claim_ids?: string[];
  order_start?: number;
  order_end?: number;
  primary_subject?: string;
  subject_key?: string;
  primary_space?: string;
  space_key?: string;
  primary_time?: string;
  time_key?: string;
  topic_key?: string;
  text?: string;
  summary?: string;
  predicates?: string[];
  space_values?: string[];
  time_values?: string[];
  confidence?: number;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

export type IngestRunTrace = {
  run_id: string;
  source_id?: string | null;
  source_name?: string | null;
  language: string;
  status: string;
  created_at: string;
  summary: {
    sentence_count: number;
    mention_count: number;
    claim_count: number;
    space_time_frame_count: number;
    semantic_block_count?: number;
    local_entity_cluster_count?: number;
    local_entity_count?: number;
    technical_entities?: number;
    technical_memory_chunks?: number;
    search_profiles?: number;
    candidate_selection_count?: number;
    candidates_found_count?: number;
    candidates_without_evidence_count?: number;
    top_candidate_score?: number;
    candidate_selection_ready?: boolean;
    similarity_analysis_count?: number;
    similarity_ready?: boolean;
    high_similarity_count?: number;
    medium_similarity_count?: number;
    low_similarity_count?: number;
    similarity_without_evidence_count?: number;
    tension_analysis_count?: number;
    hard_conflict_count?: number;
    temporal_change_count?: number;
    retrieval_chunk_count?: number;
    conflicting_chunk_count?: number;
    temporal_context_included?: boolean;
    low_coherence_local_entity_count?: number;
    unknown_entity_type_count?: number;
    quality?: {
      skipped_sentence_count?: number;
      rejected_claim_count?: number;
      describes_claim_count?: number;
      low_confidence_claim_count?: number;
      bad_subject_claim_count?: number;
      question_sentence_count?: number;
      fragment_sentence_count?: number;
      todo?: string;
    };
  };
  sentences: IngestRunTraceSentence[];
  local_entities?: IngestRunTraceLocalEntity[];
  technical_entities?: IngestRunTraceTechnicalEntity[];
  technical_memory_chunks?: IngestRunTraceTechnicalMemoryChunk[];
  search_profiles?: IngestRunTraceSearchProfile[];
  candidate_selections?: IngestRunTraceCandidateSelection[];
  similarity_analyses?: IngestRunTraceSimilarityAnalysis[];
  tension_analyses?: IngestRunTraceTensionAnalysis[];
  retrieval_chunks?: IngestRunTraceRetrievalChunk[];
  semantic_blocks?: IngestRunTraceSemanticBlock[];
  local_entity_clusters?: Record<string, unknown>[];
  local_resolver_trace?: Record<string, unknown> | null;
};

export type KnowledgeTraceOptions = {
  logLevel?: KnowledgeTraceLogLevel;
  debug?: boolean;
};

export type ParagraphItem = {
  id: string;
  source_id: string;
  document_id: string;
  block_id?: string | null;
  order_index: number;
  text_content: string;
  char_start: number;
  char_end: number;
  sentence_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type IngestRun = {
  id: string;
  corpus_uuid: string;
  input_channel: string;
  status: string;
  batch_size: number;
  queued_count: number;
  processing_count: number;
  completed_count: number;
  failed_count: number;
  duplicate_count: number;
  rejected_count: number;
  continue_on_error: boolean;
  pipeline_route: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
  metadata: Record<string, unknown>;
  items: IngestItem[];
  events: IngestEventItem[];
};

export type CreateKbPayload = {
  name: string;
  description?: string;
  permissions?: Array<{ user_id: number; permission: string }>;
};

export type UpdateKbPayload = {
  uuid: string;
  name: string;
  description?: string;
  personal_data_mode?: PersonalDataMode;
};

export type DeleteKbPayload = { uuid: string; confirm_name: string };
export type ClearKbPayload = { uuid: string; confirm_name: string };

export async function getKbList(): Promise<KbItem[]> {
  const res = await api.get("/kb");
  return res.data as KbItem[];
}

export async function createKb(body: CreateKbPayload): Promise<KbItem> {
  const res = await api.post("/kb", body);
  return res.data as KbItem;
}

export async function getKbPermissions(kbUuid: string): Promise<KbPermissionItem[]> {
  const res = await api.get(`/kb/${kbUuid}/permissions`);
  return res.data as KbPermissionItem[];
}

export type KbPermissionsBatchResponse = Record<string, KbPermissionItem[]>;

export async function getKbPermissionsBatch(kbUuids: string[]): Promise<KbPermissionsBatchResponse> {
  const unique = Array.from(new Set((kbUuids || []).map((x) => (x || "").trim()).filter(Boolean)));
  if (unique.length === 0) return {};
  const res = await api.post("/kb/permissions/batch", { uuids: unique });
  return (res.data || {}) as KbPermissionsBatchResponse;
}

export async function setKbPermissions(
  kbUuid: string,
  permissions: Array<{ user_id: number; permission: string }>
): Promise<unknown> {
  const res = await api.put(`/kb/${kbUuid}/permissions`, { permissions });
  return res.data;
}

export async function updateKb({
  uuid,
  name,
  description,
  personal_data_mode,
}: UpdateKbPayload): Promise<KbItem> {
  const body: Record<string, unknown> = {
    name,
    description,
  };
  if (personal_data_mode) {
    body.personal_data_mode = personal_data_mode;
  }
  const res = await api.put(`/kb/${uuid}`, body);
  return res.data as KbItem;
}

export async function deleteKb({ uuid, confirm_name }: DeleteKbPayload): Promise<unknown> {
  const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
  return res.data;
}

export async function clearKb({ uuid, confirm_name }: ClearKbPayload): Promise<unknown> {
  const res = await api.post(`/kb/${uuid}/clear`, { confirm_name });
  return res.data;
}

export async function createTextIngestRun(
  kbUuid: string,
  body: { text: string; title: string }
): Promise<IngestRun> {
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/text`, body);
  return res.data as IngestRun;
}

export async function createFileIngestRun(kbUuid: string, files: File[]): Promise<IngestRun> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/files`, form);
  return res.data as IngestRun;
}

export async function createUrlIngestRun(
  kbUuid: string,
  items: Array<{ url: string; title?: string }>
): Promise<IngestRun> {
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/urls`, { items });
  return res.data as IngestRun;
}

export async function listIngestRuns(kbUuid: string): Promise<IngestRun[]> {
  const res = await api.get(`/knowledge/corpora/${kbUuid}/ingest/runs`);
  return res.data as IngestRun[];
}

export async function getIngestRun(runId: string): Promise<IngestRun> {
  const res = await api.get(`/knowledge/ingest/runs/${runId}`);
  return res.data as IngestRun;
}

export async function reprocessIngestItem(itemId: string): Promise<IngestRun> {
  const res = await api.post(`/knowledge/ingest/items/${itemId}/reprocess`);
  return res.data as IngestRun;
}

export async function listIngestItemSentences(itemId: string): Promise<SentenceItem[]> {
  const res = await api.get(`/knowledge/ingest/items/${itemId}/sentences`);
  return res.data as SentenceItem[];
}

export async function getSentenceInterpretation(sentenceId: string): Promise<SentenceInterpretationDetail> {
  const res = await api.get(`/knowledge/sentences/${sentenceId}/interpretation`);
  return res.data as SentenceInterpretationDetail;
}

function traceParams(options?: KnowledgeTraceOptions): Record<string, string | boolean> {
  return {
    log_level: options?.logLevel ?? "FULL_TRACE",
    ...(options?.debug ? { debug: true } : {}),
  };
}

export async function getIngestRunTrace(runId: string, options?: KnowledgeTraceOptions): Promise<IngestRunTrace> {
  const res = await api.get(`/knowledge/dev/ingest-runs/${runId}/trace`, { params: traceParams(options) });
  return res.data as IngestRunTrace;
}

export async function updateSemanticBlockStatus(
  kbUuid: string,
  blockId: string,
  status: "draft" | "approved" | "rejected" | "withdrawn" | "outdated" | "disputed"
): Promise<{ block_id: string; status: string; interpretation_run_id: string; block: IngestRunTraceSemanticBlock }> {
  const res = await api.patch(`/knowledge/corpora/${kbUuid}/semantic-blocks/${blockId}/status`, { status });
  return res.data as { block_id: string; status: string; interpretation_run_id: string; block: IngestRunTraceSemanticBlock };
}

export async function listIngestItemParagraphs(itemId: string): Promise<ParagraphItem[]> {
  const res = await api.get(`/knowledge/ingest/items/${itemId}/paragraphs`);
  return res.data as ParagraphItem[];
}
