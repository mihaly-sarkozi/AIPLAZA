export type SentenceRow = {
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

export type ParagraphRow = {
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

export type SentenceInterpretationDetail = {
  interpretation: {
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
  mentions: Array<{
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
  }>;
  claims: Array<{
    id: string;
    sentence_id: string;
    subject_text: string;
    predicate_text: string;
    object_text?: string | null;
    claim_type: string;
    assertion_mode: string;
    time_mode: string;
    time_label?: string | null;
    space_mode: string;
    space_label?: string | null;
    confidence: number;
    created_at: string;
    metadata: Record<string, unknown>;
  }>;
};

export type StructureDbDetail = {
  title: string;
  description?: string;
  data: Record<string, unknown>;
};
