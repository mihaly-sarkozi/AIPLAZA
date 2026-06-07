import api from "../../axiosClient";
import { getTrainingBatch, submitTextTraining, trainingSubmitToIngestRun } from "./kbTrainingApi";
import type { FileIngestEstimate, IngestRun, IngestRunListResponse, TrainingSubmitResponse } from "./types";

/** @deprecated Használd a `submitTextTraining` függvényt a `kbTrainingApi`-ból. */
export async function createTextIngestRun(
  kbUuid: string,
  body: { content: string; title?: string | null }
): Promise<IngestRun> {
  const res = await api.post(`/kb/${kbUuid}/training/text`, body);
  return trainingSubmitToIngestRun(res.data as TrainingSubmitResponse, kbUuid);
}

export { getTrainingBatch, submitTextTraining };

export async function createFileIngestRun(kbUuid: string, files: File[], characterCounts?: number[]): Promise<IngestRun> {
  const form = new FormData();
  files.forEach((file, index) => {
    form.append("files", file);
    const count = Math.max(0, Math.round(Number(characterCounts?.[index] ?? 0)));
    if (count > 0) form.append("character_counts", String(count));
  });
  const res = await api.post(`/kb/${kbUuid}/ingest/files`, form);
  return res.data as IngestRun;
}

export async function estimateFileIngestRun(kbUuid: string, files: File[]): Promise<FileIngestEstimate> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/kb/${kbUuid}/ingest/files/estimate`, form);
  return res.data as FileIngestEstimate;
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
  const res = await api.get(`/kb/${kbUuid}/ingest/runs`, { params });
  return res.data as IngestRunListResponse;
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
