import api from "../../axiosClient";

export type ProcessingEventSummary = {
  id: string;
  knowledge_base_id: string;
  training_batch_id?: string | null;
  training_item_id?: string | null;
  job_id?: string | null;
  module: string;
  stage: string;
  step: string;
  event_type: string;
  status: string;
  message?: string | null;
  duration_ms?: number | null;
  input_summary_json: Record<string, unknown>;
  output_summary_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type ProcessingEventsPage = {
  items: ProcessingEventSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type ProcessingIssueSummary = {
  id: string;
  knowledge_base_id: string;
  training_item_id?: string | null;
  job_id?: string | null;
  module: string;
  stage: string;
  step?: string | null;
  severity: string;
  issue_code: string;
  issue_message?: string | null;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
  metadata_json: Record<string, unknown>;
};

export type ProcessingIssuesPage = {
  items: ProcessingIssueSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type UnderstandingJobSummary = {
  id: string;
  training_item_id: string;
  training_batch_id: string;
  knowledge_base_id: string;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  retryable: boolean;
  retry_count: number;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

export type UnderstandingStepSummary = {
  step: string;
  status: string;
  duration_ms: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string | null;
};

export type UnderstandingStatusResponse = {
  job: UnderstandingJobSummary | null;
  steps: UnderstandingStepSummary[];
  chunk_count: number;
};

export type ProcessingMetricsResponse = {
  documents_total: number;
  documents_ingested: number;
  documents_understanding_ready: number;
  documents_discovery_ready: number;
  documents_indexed: number;
  documents_failed: number;
  documents_partial: number;
  chunks_total: number;
  issues_open: number;
  issues_warning: number;
  issues_error: number;
  issues_critical: number;
  last_processed_at?: string | null;
  last_failed_at?: string | null;
};

export type ListProcessingEventsParams = {
  training_item_id?: string;
  job_id?: string;
  module?: string;
  limit?: number;
  offset?: number;
};

export async function listProcessingEvents(
  kbUuid: string,
  params?: ListProcessingEventsParams
): Promise<ProcessingEventsPage> {
  const res = await api.get(`/kb/${kbUuid}/processing/events`, { params });
  return res.data as ProcessingEventsPage;
}

export async function listProcessingIssues(
  kbUuid: string,
  params?: {
    training_item_id?: string;
    status?: string;
    severity?: string;
    limit?: number;
    offset?: number;
  }
): Promise<ProcessingIssuesPage> {
  const res = await api.get(`/kb/${kbUuid}/processing/issues`, { params });
  return res.data as ProcessingIssuesPage;
}

export async function getProcessingMetrics(kbUuid: string): Promise<ProcessingMetricsResponse | null> {
  try {
    const res = await api.get(`/kb/${kbUuid}/processing/metrics`);
    return res.data as ProcessingMetricsResponse;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) return null;
    throw error;
  }
}

export async function getUnderstandingStatus(
  kbUuid: string,
  itemId: string
): Promise<UnderstandingStatusResponse> {
  const res = await api.get(`/kb/${kbUuid}/understanding/items/${itemId}`);
  return res.data as UnderstandingStatusResponse;
}
