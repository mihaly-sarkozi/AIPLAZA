import api from "../../axiosClient";
import type { FileIngestEstimate, IngestRun, IngestRunListResponse } from "./types";

export async function createTextIngestRun(
  kbUuid: string,
  body: { text: string; title: string }
): Promise<IngestRun> {
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/text`, body);
  return res.data as IngestRun;
}

export async function createFileIngestRun(kbUuid: string, files: File[], characterCounts?: number[]): Promise<IngestRun> {
  const form = new FormData();
  files.forEach((file, index) => {
    form.append("files", file);
    const count = Math.max(0, Math.round(Number(characterCounts?.[index] ?? 0)));
    if (count > 0) form.append("character_counts", String(count));
  });
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/files`, form);
  return res.data as IngestRun;
}

export async function estimateFileIngestRun(kbUuid: string, files: File[]): Promise<FileIngestEstimate> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/files/estimate`, form);
  return res.data as FileIngestEstimate;
}

export async function createUrlIngestRun(
  kbUuid: string,
  items: Array<{ url: string; title?: string }>
): Promise<IngestRun> {
  const res = await api.post(`/knowledge/corpora/${kbUuid}/ingest/urls`, { items });
  return res.data as IngestRun;
}

export async function listIngestRuns(
  kbUuid: string,
  params?: { limit?: number; offset?: number }
): Promise<IngestRunListResponse> {
  const res = await api.get(`/knowledge/corpora/${kbUuid}/ingest/runs`, { params });
  return res.data as IngestRunListResponse;
}

export async function getIngestRun(runId: string): Promise<IngestRun> {
  const res = await api.get(`/knowledge/ingest/runs/${runId}`);
  return res.data as IngestRun;
}

export async function reprocessIngestItem(itemId: string): Promise<IngestRun> {
  const res = await api.post(`/knowledge/ingest/items/${itemId}/reprocess`);
  return res.data as IngestRun;
}
