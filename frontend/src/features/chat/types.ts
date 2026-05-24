/** Chat feature types. */
export type ChatEvidenceItem = {
  claim_id?: string;
  sentence_id?: string;
  source_id?: string;
  claim_text?: string;
  sentence_text?: string;
  [key: string]: unknown;
};

export type ChatSourceItem = {
  kb_uuid: string;
  kb_name?: string;
  point_id: string;
  source_id?: string;
  title?: string;
  snippet?: string;
  source_type?: string;
  file_ref?: string | null;
  display_type?: string;
  created_by?: number | null;
  created_by_label?: string;
  created_at?: string | null;
};

export type RestoredPiiSpan = {
  start: number;
  end: number;
  token?: string;
  value?: string;
  entity_type?: string;
};

export type ChatApiResponse = {
  answer: string;
  query_run_id?: string | null;
  answer_mode?: string;
  answer_source?: string;
  confidence?: number;
  evidence?: ChatEvidenceItem[];
  cited_claim_ids?: string[];
  cited_sentence_ids?: string[];
  cited_source_ids?: string[];
  query_profile?: Record<string, unknown>;
  matched_chunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  context_blocks?: Array<Record<string, unknown>>;
  sources?: ChatSourceItem[];
  prompt_context?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
  encoded_prompt_context?: string;
  restored_pii_spans?: RestoredPiiSpan[];
};

export type ChatApiRequest = {
  question: string;
  kb_uuid?: string;
  debug?: boolean;
  conversation_history?: Array<{ role: "user" | "assistant"; content: string }>;
  retrieval_history?: string[];
};

export type ChatMessageType = {
  role: string;
  text: string;
  aiContextContent?: string;
  excludeFromAiContext?: boolean;
  question?: string;
  queryRunId?: string | null;
  answerMode?: string;
  answerSource?: string;
  confidence?: number;
  evidence?: ChatEvidenceItem[];
  citedClaimIds?: string[];
  citedSentenceIds?: string[];
  citedSourceIds?: string[];
  queryProfile?: Record<string, unknown>;
  matchedChunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  contextBlocks?: Array<Record<string, unknown>>;
  sources?: ChatSourceItem[];
  promptContext?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
  encodedPromptContext?: string;
  restoredPiiSpans?: RestoredPiiSpan[];
  actionLabel?: string;
  actionHref?: string;
  progressPercent?: number | null;
};

export type PersistedChatSession = {
  messages: ChatMessageType[];
  contextNotice: string | null;
  draft: string;
  chatMode?: "query" | "train";
  selectedChatKbUuid?: string;
  selectedTrainKbUuid?: string;
  activeTrainingRunId?: string;
  activeTrainingTitle?: string | null;
  trainingVisualProgress?: number;
  trainingStartedAt?: number | null;
  trainingEstimatedDurationMs?: number | null;
};

export type PendingFileTraining = {
  file: File;
  kbUuid: string;
  title: string;
  characterCount: number;
};

export type PendingTextTraining = {
  kbUuid: string;
  title: string;
  text: string;
};

export type FileCountingProgress = {
  filename: string;
  percent: number;
  estimatedCharacters: number;
};
