export type PersonalDataMode = "no_personal_data" | "with_confirmation" | "allowed_not_to_ai" | "no_pii_filter";

export type KbItem = {
  uuid: string;
  name: string;
  description?: string;
  personal_data_mode: PersonalDataMode;
  pii_depersonalization_enabled?: boolean;
  is_public?: boolean;
  public_enabled?: boolean;
  storage_metrics?: {
    file_bytes?: number;
    database_bytes?: number;
    qdrant_bytes?: number;
    total_bytes?: number;
    qdrant_points?: number;
    qdrant_vectors?: number;
    training_char_count?: number;
  };
  status?: "active" | "deleted" | string;
  deleted_at?: string | null;
  can_train?: boolean;
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

export type TrainingItemSummaryApi = {
  id: string;
  input_type: string;
  title: string;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  char_count?: number | null;
};

export type TrainingBatchSummaryApi = {
  id: string;
  knowledge_base_id: string;
  input_channel: string;
  status: string;
  batch_size: number;
  accepted_count: number;
  failed_count: number;
  rejected_count: number;
  duplicate_count: number;
  created_at: string;
  completed_at?: string | null;
  progress?: Record<string, unknown> | null;
};

export type TrainingTextResponse = {
  batch_id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  batch_size?: number;
  accepted_count?: number;
  failed_count?: number;
  duplicate_count?: number;
  rejected_count?: number;
  items?: TrainingItemSummaryApi[];
};

export type TrainingBatchStatusResponse = {
  batch: TrainingBatchSummaryApi;
  items: TrainingItemSummaryApi[];
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
  created_by?: number | null;
  created_by_label?: string | null;
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
  created_by?: number | null;
  created_by_label?: string | null;
  metadata: Record<string, unknown>;
  items: IngestItem[];
  events: IngestEventItem[];
};

export type IngestRunListSummary = {
  total_run_count: number;
  total_item_count: number;
  total_char_count: number;
  total_sentence_count: number;
};

export type FileIngestEstimate = {
  file_count: number;
  total_char_count: number;
  total_storage_bytes: number;
  can_start: boolean;
  reason?: string | null;
  items: Array<{
    filename: string;
    mime_type?: string | null;
    char_count: number;
    storage_bytes: number;
  }>;
};

export type IngestRunListResponse = {
  items: IngestRun[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  summary: IngestRunListSummary;
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
  pii_depersonalization_enabled?: boolean;
  public_enabled?: boolean;
};

export type DeleteKbPayload = { uuid: string; confirm_name: string };
export type KbPermissionsBatchResponse = Record<string, KbPermissionItem[]>;

export * from "./traceTypes";
