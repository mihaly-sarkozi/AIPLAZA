import api from "../../axiosClient";
import type { IngestRunTrace, IngestRunTraceSemanticBlock, KnowledgeTraceOptions } from "./types";

function traceParams(options?: KnowledgeTraceOptions): Record<string, string | boolean> {
  return {
    log_level: options?.logLevel ?? "FULL_TRACE",
    ...(options?.debug ? { debug: true } : {}),
  };
}

export async function getIngestRunTrace(runId: string, options?: KnowledgeTraceOptions): Promise<IngestRunTrace> {
  const res = await api.get(`/knowledge/dev/ingest-runs/${runId}/trace`, { params: traceParams(options) });
  return res.data as IngestRunTrace;
}

export async function updateSemanticBlockStatus(
  kbUuid: string,
  blockId: string,
  status: "draft" | "approved" | "rejected" | "withdrawn" | "outdated" | "disputed"
): Promise<{ block_id: string; status: string; interpretation_run_id: string; block: IngestRunTraceSemanticBlock }> {
  const res = await api.patch(`/knowledge/corpora/${kbUuid}/semantic-blocks/${blockId}/status`, { status });
  return res.data as { block_id: string; status: string; interpretation_run_id: string; block: IngestRunTraceSemanticBlock };
}
