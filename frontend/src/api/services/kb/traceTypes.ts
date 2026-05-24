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

export type KnowledgeTraceLogLevel = "SUMMARY" | "INSPECT" | "FULL_TRACE";

export type KnowledgeTraceOptions = {
  logLevel?: KnowledgeTraceLogLevel;
  debug?: boolean;
};
