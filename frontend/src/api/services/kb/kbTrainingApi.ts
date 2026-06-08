import api from "../../axiosClient";
import { normalizeTrainingBatchStatus, normalizeTrainingTextResponse } from "./normalizeTrainingBatch";
import type {
  FileIngestEstimate,
  IngestRun,
  TrainingBatchStatusResponse,
  TrainingTextResponse,
} from "./types";

export type SubmitTextTrainingPayload = {
  content: string;
  title?: string | null;
};

export type SubmitTextTrainingResult = {
  batchId: string;
  status: string;
  createdAt: string;
  completedAt: string | null;
};

/** Szöveges tanítás indítása — `POST /api/kb/{kbUuid}/training/text` */
export async function submitTextTraining(
  kbUuid: string,
  body: SubmitTextTrainingPayload
): Promise<SubmitTextTrainingResult> {
  const res = await api.post(`/kb/${kbUuid}/training/text`, body);
  const data = res.data as TrainingTextResponse;
  return {
    batchId: data.batch_id,
    status: data.status,
    createdAt: data.created_at,
    completedAt: data.completed_at ?? null,
  };
}

/** Beküldés válasz → minimális IngestRun stub (cache / lista frissítéshez). */
export function trainingTextResponseToIngestRun(data: TrainingTextResponse, kbUuid: string): IngestRun {
  const partial = normalizeTrainingTextResponse(data, kbUuid);
  return {
    input_channel: "text",
    queued_count: 0,
    processing_count: 0,
    continue_on_error: false,
    pipeline_route: "default",
    ...partial,
  };
}

export function trainingFileResponseToIngestRun(data: TrainingTextResponse, kbUuid: string): IngestRun {
  const partial = normalizeTrainingTextResponse(data, kbUuid);
  return {
    input_channel: "file",
    queued_count: 0,
    processing_count: 0,
    continue_on_error: false,
    pipeline_route: "default",
    ...partial,
  };
}

/** Fájl tanítás becslés — `POST /api/kb/{kbUuid}/training/files/estimate` */
export async function estimateFileTraining(kbUuid: string, files: File[]): Promise<FileIngestEstimate> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/kb/${kbUuid}/training/files/estimate`, form);
  return res.data as FileIngestEstimate;
}

/** Fájlos tanítás indítása — `POST /api/kb/{kbUuid}/training/files` */
export async function submitFileTraining(kbUuid: string, files: File[]): Promise<SubmitTextTrainingResult> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/kb/${kbUuid}/training/files`, form);
  const data = res.data as TrainingTextResponse;
  return {
    batchId: data.batch_id,
    status: data.status,
    createdAt: data.created_at,
    completedAt: data.completed_at ?? null,
  };
}

/** Training batch lekérdezése — `GET /api/kb/training/batches/{batchId}` */
export async function getTrainingBatch(batchId: string): Promise<IngestRun> {
  const res = await api.get(`/kb/training/batches/${batchId}`);
  return normalizeTrainingBatchStatus(res.data as TrainingBatchStatusResponse);
}
