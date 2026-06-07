import api from "../../axiosClient";
import { normalizeTrainingBatchStatus, normalizeTrainingSubmit } from "./normalizeTrainingBatch";
import type { IngestRun, TrainingBatchStatusResponse, TrainingSubmitResponse } from "./types";

export type SubmitTextTrainingPayload = {
  content: string;
  title?: string | null;
};

export type SubmitTextTrainingResult = {
  batchId: string;
  status: string;
};

/** Szöveges tanítás indítása — `POST /api/kb/{kbUuid}/training/text` */
export async function submitTextTraining(
  kbUuid: string,
  body: SubmitTextTrainingPayload
): Promise<SubmitTextTrainingResult> {
  const res = await api.post(`/kb/${kbUuid}/training/text`, body);
  const data = res.data as TrainingSubmitResponse;
  return {
    batchId: data.batch_id,
    status: data.status,
  };
}

/** Beküldés válasz → minimális IngestRun stub (cache / lista frissítéshez). */
export function trainingSubmitToIngestRun(data: TrainingSubmitResponse, kbUuid: string): IngestRun {
  const partial = normalizeTrainingSubmit(data, kbUuid);
  return {
    input_channel: "text",
    queued_count: 0,
    processing_count: 0,
    continue_on_error: false,
    pipeline_route: "default",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: null,
    ...partial,
  };
}

/** Training batch lekérdezése — `GET /api/kb/training/batches/{batchId}` */
export async function getTrainingBatch(batchId: string): Promise<IngestRun> {
  const res = await api.get(`/kb/training/batches/${batchId}`);
  return normalizeTrainingBatchStatus(res.data as TrainingBatchStatusResponse);
}
