import api from "../../axiosClient";
import {
  estimateFileTraining,
  getTrainingBatch,
  submitFileTraining,
  submitTextTraining,
  trainingFileResponseToIngestRun,
  trainingTextResponseToIngestRun,
} from "./kbTrainingApi";
import type { FileIngestEstimate, IngestRun, IngestRunListResponse, TrainingTextResponse } from "./types";

/** @deprecated Használd a `submitTextTraining` függvényt a `kbTrainingApi`-ból. */
export async function createTextIngestRun(
  kbUuid: string,
  body: { content: string; title?: string | null }
): Promise<IngestRun> {
  const res = await api.post(`/kb/${kbUuid}/training/text`, body);
  return trainingTextResponseToIngestRun(res.data as TrainingTextResponse, kbUuid);
}

export { estimateFileTraining, getTrainingBatch, submitFileTraining, submitTextTraining };

/** @deprecated Használd a `submitFileTraining` függvényt a `kbTrainingApi`-ból. */
export async function createFileIngestRun(
  kbUuid: string,
  files: File[],
  _characterCounts?: number[]
): Promise<IngestRun> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/kb/${kbUuid}/training/files`, form);
  return trainingFileResponseToIngestRun(res.data as TrainingTextResponse, kbUuid);
}

/** @deprecated Használd az `estimateFileTraining` függvényt a `kbTrainingApi`-ból. */
export async function estimateFileIngestRun(kbUuid: string, files: File[]): Promise<FileIngestEstimate> {
  return estimateFileTraining(kbUuid, files);
}

export async function createUrlIngestRun(
  kbUuid: string,
  items: Array<{ url: string; title?: string }>
): Promise<IngestRun> {
  const res = await api.post(`/kb/${kbUuid}/ingest/urls`, { items });
  return res.data as IngestRun;
}

export async function listIngestRuns(
  kbUuid: string,
  params?: { limit?: number; offset?: number }
): Promise<IngestRunListResponse> {
  try {
    const res = await api.get(`/kb/${kbUuid}/ingest/runs`, { params });
    return res.data as IngestRunListResponse;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) {
      return {
        items: [],
        total_count: 0,
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
        has_more: false,
        summary: {
          total_run_count: 0,
          total_item_count: 0,
          total_char_count: 0,
          total_sentence_count: 0,
        },
      };
    }
    throw error;
  }
}

function isTrainingBatchRunId(runId: string): boolean {
  return runId.startsWith("training_batch_");
}

export async function getIngestRun(runId: string): Promise<IngestRun> {
  if (isTrainingBatchRunId(runId)) {
    return getTrainingBatch(runId);
  }
  try {
    const res = await api.get(`/kb/ingest/runs/${runId}`);
    return res.data as IngestRun;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) {
      return getTrainingBatch(runId);
    }
    throw error;
  }
}

export async function reprocessIngestItem(itemId: string): Promise<IngestRun> {
  const res = await api.post(`/knowledge/ingest/items/${itemId}/reprocess`);
  return res.data as IngestRun;
}
