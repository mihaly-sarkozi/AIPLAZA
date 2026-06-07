import type {
  IngestItem,
  IngestRun,
  TrainingBatchStatusResponse,
  TrainingItemSummaryApi,
  TrainingSubmitResponse,
} from "./types";

function mapTrainingItem(item: TrainingItemSummaryApi, index: number, batchId: string, kbId: string): IngestItem {
  const charCount = item.char_count ?? null;
  return {
    id: item.id,
    ingest_run_id: batchId,
    corpus_uuid: kbId,
    queue_order: index,
    input_type: item.input_type,
    display_name: item.title || item.input_type,
    title: item.title,
    status: item.status,
    error_code: item.error_code ?? null,
    error_message: item.error_message ?? null,
    duplicate_of_item_id: null,
    pipeline_route: "default",
    content_hash: null,
    created_at: new Date(0).toISOString(),
    updated_at: new Date(0).toISOString(),
    metadata: charCount != null ? { char_count: charCount } : {},
  };
}

function completedCountFromBatch(batch: TrainingBatchStatusResponse["batch"]): number {
  if (batch.status === "completed" || batch.status === "partial_success") {
    return Math.max(batch.accepted_count, 1);
  }
  return batch.accepted_count;
}

export function normalizeTrainingBatchStatus(data: TrainingBatchStatusResponse): IngestRun {
  const batch = data.batch;
  const progress = batch.progress ?? undefined;
  return {
    id: batch.id,
    corpus_uuid: batch.knowledge_base_id,
    input_channel: batch.input_channel,
    status: batch.status,
    batch_size: batch.batch_size,
    queued_count: 0,
    processing_count: 0,
    completed_count: completedCountFromBatch(batch),
    failed_count: batch.failed_count,
    duplicate_count: batch.duplicate_count,
    rejected_count: batch.rejected_count,
    continue_on_error: false,
    pipeline_route: "default",
    created_at: batch.created_at,
    completed_at: batch.completed_at ?? null,
    updated_at: batch.completed_at ?? batch.created_at,
    created_by: undefined,
    metadata: progress ? { progress_summary: progress } : {},
    items: (data.items ?? []).map((item, index) => mapTrainingItem(item, index, batch.id, batch.knowledge_base_id)),
    events: [],
  };
}

export function normalizeTrainingSubmit(
  data: TrainingSubmitResponse,
  kbUuid: string
): Pick<IngestRun, "id" | "status" | "corpus_uuid" | "batch_size" | "completed_count" | "failed_count" | "duplicate_count" | "rejected_count" | "items" | "metadata" | "events"> & {
  id: string;
} {
  const items = (data.items ?? []).map((item, index) => mapTrainingItem(item, index, data.batch_id, kbUuid));
  return {
    id: data.batch_id,
    status: data.status,
    corpus_uuid: kbUuid,
    batch_size: data.batch_size ?? 1,
    completed_count: data.accepted_count ?? (data.status === "completed" ? 1 : 0),
    failed_count: data.failed_count ?? 0,
    duplicate_count: data.duplicate_count ?? 0,
    rejected_count: data.rejected_count ?? 0,
    items,
    metadata: {},
    events: [],
  };
}
