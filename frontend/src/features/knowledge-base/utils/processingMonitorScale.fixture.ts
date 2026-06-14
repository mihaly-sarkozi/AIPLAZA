import type { ProcessingEventSummary } from "../../../api/services/kb/kbProcessingApi";

/** Valós mihaly2 tenant futás (2026-06-14) — kalibrációs referencia. */
export const REAL_COMPLETED_RUN_ITEM_ID = "training_item_2126c47aceab42709f1bceeda1d81df5";

export const REAL_COMPLETED_RUN_DURATIONS: Array<{
  module: string;
  step: string;
  duration_ms: number;
}> = [
  { module: "kb_understanding", step: "EXTRACT_CONTENT", duration_ms: 53761 },
  { module: "kb_understanding", step: "NORMALIZE_PARTS", duration_ms: 91 },
  { module: "kb_understanding", step: "BUILD_CHUNKS", duration_ms: 46 },
  { module: "kb_understanding", step: "VALIDATE_RESULT", duration_ms: 12 },
  { module: "kb_discovery", step: "DETECT_LANGUAGE", duration_ms: 82 },
  { module: "kb_discovery", step: "EXTRACT_ENTITIES", duration_ms: 495 },
  { module: "kb_discovery", step: "ENRICH_LOCAL", duration_ms: 954 },
  { module: "kb_discovery", step: "EXTRACT_TEMPORAL", duration_ms: 16 },
  { module: "kb_discovery", step: "EXTRACT_SPATIAL", duration_ms: 15 },
  { module: "kb_discovery", step: "EXTRACT_PROCESS", duration_ms: 14 },
  { module: "kb_discovery", step: "BUILD_RELATIONSHIPS", duration_ms: 361 },
  { module: "kb_discovery", step: "SCORE_KNOWLEDGE", duration_ms: 11 },
  { module: "kb_discovery", step: "VALIDATE_DISCOVERY", duration_ms: 67 },
  { module: "kb_discovery", step: "PIPELINE", duration_ms: 0 },
  { module: "kb_embedding", step: "GENERATE", duration_ms: 207858 },
  { module: "kb_embedding", step: "PIPELINE", duration_ms: 207863 },
  { module: "kb_indexing", step: "ENSURE_COLLECTION", duration_ms: 1193 },
  { module: "kb_indexing", step: "UPSERT", duration_ms: 2054 },
  { module: "kb_indexing", step: "PIPELINE", duration_ms: 2675 },
];

export const REAL_COMPLETED_RUN_TIMESTAMPS: Record<string, string> = {
  start: "2026-06-14T12:18:16.812Z",
  understanding_done: "2026-06-14T12:19:10.739Z",
  discovery_done: "2026-06-14T12:19:13.115Z",
  embedding_mid: "2026-06-14T12:21:00.978Z",
  embedding_done: "2026-06-14T12:22:41.032Z",
  indexing_done: "2026-06-14T12:22:43.733Z",
};

export function buildRealCompletedRunEvents(): ProcessingEventSummary[] {
  let seq = 0;
  const events: ProcessingEventSummary[] = [
    {
      id: `real-${(seq += 1)}`,
      knowledge_base_id: "kb",
      training_item_id: REAL_COMPLETED_RUN_ITEM_ID,
      module: "kb_understanding",
      stage: "EXTRACT",
      step: "EXTRACT_CONTENT",
      event_type: "EXTRACT_STARTED",
      status: "started",
      input_summary_json: {},
      output_summary_json: {},
      metadata_json: {},
      created_at: REAL_COMPLETED_RUN_TIMESTAMPS.start,
    },
    {
      id: `real-${(seq += 1)}`,
      knowledge_base_id: "kb",
      training_item_id: REAL_COMPLETED_RUN_ITEM_ID,
      module: "kb_discovery",
      stage: "DISCOVERY",
      step: "PIPELINE",
      event_type: "DISCOVERY_STARTED",
      status: "started",
      input_summary_json: {},
      output_summary_json: {},
      metadata_json: {},
      created_at: "2026-06-14T12:19:11.055Z",
    },
    {
      id: `real-${(seq += 1)}`,
      knowledge_base_id: "kb",
      training_item_id: REAL_COMPLETED_RUN_ITEM_ID,
      module: "kb_embedding",
      stage: "EMBEDDING",
      step: "PIPELINE",
      event_type: "EMBEDDING_STARTED",
      status: "started",
      input_summary_json: {},
      output_summary_json: {},
      metadata_json: {},
      created_at: "2026-06-14T12:19:13.171Z",
    },
    {
      id: `real-${(seq += 1)}`,
      knowledge_base_id: "kb",
      training_item_id: REAL_COMPLETED_RUN_ITEM_ID,
      module: "kb_indexing",
      stage: "INDEXING",
      step: "PIPELINE",
      event_type: "INDEXING_STARTED",
      status: "started",
      input_summary_json: {},
      output_summary_json: {},
      metadata_json: {},
      created_at: "2026-06-14T12:22:41.058Z",
    },
  ];

  const discoveryStepTimes: Record<string, string> = {
    DETECT_LANGUAGE: "2026-06-14T12:19:11.140Z",
    EXTRACT_ENTITIES: "2026-06-14T12:19:11.640Z",
    ENRICH_LOCAL: "2026-06-14T12:19:12.600Z",
    EXTRACT_TEMPORAL: "2026-06-14T12:19:12.620Z",
    EXTRACT_SPATIAL: "2026-06-14T12:19:12.639Z",
    EXTRACT_PROCESS: "2026-06-14T12:19:12.657Z",
    BUILD_RELATIONSHIPS: "2026-06-14T12:19:13.023Z",
    SCORE_KNOWLEDGE: "2026-06-14T12:19:13.039Z",
    VALIDATE_DISCOVERY: REAL_COMPLETED_RUN_TIMESTAMPS.discovery_done,
    PIPELINE: REAL_COMPLETED_RUN_TIMESTAMPS.discovery_done,
  };

  for (const row of REAL_COMPLETED_RUN_DURATIONS) {
    events.push({
      id: `real-${(seq += 1)}`,
      knowledge_base_id: "kb",
      training_item_id: REAL_COMPLETED_RUN_ITEM_ID,
      module: row.module,
      stage: row.step,
      step: row.step,
      event_type: `${row.step}_COMPLETED`,
      status: "completed",
      duration_ms: row.duration_ms,
      input_summary_json: {},
      output_summary_json: {},
      metadata_json: {},
      created_at:
        row.step === "EXTRACT_CONTENT"
          ? REAL_COMPLETED_RUN_TIMESTAMPS.understanding_done
          : row.module === "kb_discovery"
            ? discoveryStepTimes[row.step] ?? REAL_COMPLETED_RUN_TIMESTAMPS.discovery_done
            : row.module === "kb_embedding" && row.step === "PIPELINE"
              ? REAL_COMPLETED_RUN_TIMESTAMPS.embedding_done
              : row.module === "kb_embedding" && row.step === "GENERATE"
                ? REAL_COMPLETED_RUN_TIMESTAMPS.embedding_done
                : row.module === "kb_indexing" && row.step === "PIPELINE"
                  ? REAL_COMPLETED_RUN_TIMESTAMPS.indexing_done
                  : row.module === "kb_indexing"
                    ? REAL_COMPLETED_RUN_TIMESTAMPS.indexing_done
                    : REAL_COMPLETED_RUN_TIMESTAMPS.understanding_done,
    });
  }

  return events;
}
