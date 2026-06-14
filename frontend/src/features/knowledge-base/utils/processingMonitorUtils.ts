import type { IngestItem, IngestRun } from "../../../api/services/kb/types";
import type {
  ProcessingEventSummary,
  ProcessingIssueSummary,
  UnderstandingStepSummary,
} from "../../../api/services/kb/kbProcessingApi";
import {
  catalogKey,
  PROCESSING_PIPELINE_CATALOG,
} from "./processingPipelineCatalog";

export type ProcessingFlowStatus = "completed" | "failed" | "running" | "partial" | "unknown";

const BLOCKING_ISSUE_SEVERITIES = new Set(["ERROR", "CRITICAL"]);

/** Nyitott, feldolgozást blokkoló issue (hiba/kritikus) — figyelmeztetés nem számít. */
export function isOpenBlockingIssue(issue: ProcessingIssueSummary): boolean {
  return issue.status === "OPEN" && BLOCKING_ISSUE_SEVERITIES.has(issue.severity);
}

export function countOpenBlockingIssues(issues: ProcessingIssueSummary[]): number {
  return issues.filter(isOpenBlockingIssue).length;
}

export type ProcessingFlowSummary = {
  itemId: string;
  title: string;
  inputType: string;
  charCount: number | null;
  lastEventAt: string | null;
  status: ProcessingFlowStatus;
  completedSteps: number;
  failedSteps: number;
  openIssues: number;
  latestMessage: string | null;
  activeModule: string | null;
  activeStage: string | null;
  activeStep: string | null;
  activeEventType: string | null;
  progressPercent: number | null;
  progressTotalSteps: number | null;
  progressBatchDone: number | null;
  progressBatchTotal: number | null;
};

export type ProcessingStepRow = {
  key: string;
  module: string;
  stage: string;
  step: string;
  status: string;
  durationMs: number | null;
  createdAt: string;
  message: string | null;
  errorCode: string | null;
  inputSummary: Record<string, unknown>;
  outputSummary: Record<string, unknown>;
  eventType: string;
  isPending?: boolean;
  catalogOrder: number;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "skipped"]);

function normalizeStatus(status: string | null | undefined): string {
  return String(status ?? "").trim().toLowerCase();
}

/** Esemény / issue csoportosítási kulcs: training_item_id, metadata, vagy job_id fallback. */
export function resolveFlowItemId(
  row: Pick<ProcessingEventSummary, "training_item_id" | "job_id" | "metadata_json">,
): string | null {
  const itemId = String(row.training_item_id ?? "").trim();
  if (itemId) return itemId;
  const metaItemId = String(row.metadata_json?.training_item_id ?? "").trim();
  if (metaItemId) return metaItemId;
  const jobId = String(row.job_id ?? "").trim();
  if (jobId) return `job:${jobId}`;
  return null;
}

function stepKey(module: string, step: string): string {
  return catalogKey(module, step);
}

function emptyPendingRow(entry: typeof PROCESSING_PIPELINE_CATALOG[number], order: number): ProcessingStepRow {
  return {
    key: stepKey(entry.module, entry.step),
    module: entry.module,
    stage: entry.stage,
    step: entry.step,
    status: "pending",
    durationMs: null,
    createdAt: "",
    message: null,
    errorCode: null,
    inputSummary: {},
    outputSummary: {},
    eventType: "",
    isPending: true,
    catalogOrder: order,
  };
}

export function buildItemCatalogFromRuns(runs: IngestRun[]): Map<string, { title: string; inputType: string; charCount: number | null }> {
  const catalog = new Map<string, { title: string; inputType: string; charCount: number | null }>();
  for (const run of runs) {
    for (const item of run.items ?? []) {
      const ingestItem = item as IngestItem;
      catalog.set(ingestItem.id, {
        title: ingestItem.title || ingestItem.display_name || ingestItem.id,
        inputType: ingestItem.input_type || "unknown",
        charCount:
          typeof ingestItem.metadata?.char_count === "number"
            ? ingestItem.metadata.char_count
            : null,
      });
    }
  }
  return catalog;
}

function enrichCatalogFromEvents(
  catalog: Map<string, { title: string; inputType: string; charCount: number | null }>,
  events: ProcessingEventSummary[],
): void {
  for (const event of events) {
    const itemId = resolveFlowItemId(event);
    if (!itemId || catalog.has(itemId)) continue;
    const title =
      String(event.metadata_json?.title ?? event.metadata_json?.display_name ?? "").trim() ||
      (itemId.startsWith("job:") ? itemId.slice(4) : itemId);
    catalog.set(itemId, {
      title,
      inputType: String(event.metadata_json?.input_type ?? "unknown"),
      charCount: null,
    });
  }
}

const PIPELINE_MODULE_ORDER = [
  "kb_understanding",
  "kb_discovery",
  "kb_embedding",
  "kb_indexing",
] as const;

export function deriveFlowStatus(events: ProcessingEventSummary[], issues: ProcessingIssueSummary[]): ProcessingFlowStatus {
  const terminal = events.filter((event) => TERMINAL_STATUSES.has(normalizeStatus(event.status)));
  if (terminal.some((event) => normalizeStatus(event.status) === "failed")) return "failed";
  if (issues.some(isOpenBlockingIssue)) return "failed";

  const hasIndexingDone = terminal.some(
    (event) =>
      event.module === "kb_indexing" &&
      event.step === "PIPELINE" &&
      normalizeStatus(event.status) === "completed",
  );
  if (hasIndexingDone) return "completed";

  const hasEmbeddingDone = terminal.some(
    (event) =>
      event.module === "kb_embedding" &&
      event.step === "PIPELINE" &&
      normalizeStatus(event.status) === "completed"
  );
  const hasDiscoveryDone = terminal.some(
    (event) =>
      event.module === "kb_discovery" &&
      event.step === "PIPELINE" &&
      normalizeStatus(event.status) === "completed"
  );
  const hasUnderstandingDone = terminal.some(
    (event) =>
      event.module === "kb_understanding" &&
      event.step === "PIPELINE" &&
      normalizeStatus(event.status) === "completed"
  );
  if (hasEmbeddingDone || hasDiscoveryDone || hasUnderstandingDone) return "running";

  if (!hasIndexingDone) {
    if (events.some((event) => normalizeStatus(event.status) === "started")) return "running";
    for (const moduleName of PIPELINE_MODULE_ORDER) {
      const modEvents = events.filter((event) => event.module === moduleName);
      if (!modEvents.length) continue;
      const pipelineTerminal = modEvents.some(
        (event) => event.step === "PIPELINE" && TERMINAL_STATUSES.has(normalizeStatus(event.status)),
      );
      if (
        !pipelineTerminal &&
        modEvents.some((event) => TERMINAL_STATUSES.has(normalizeStatus(event.status)))
      ) {
        return "running";
      }
    }
  }

  const hasPipelineDone = terminal.some(
    (event) => event.step === "PIPELINE" && normalizeStatus(event.status) === "completed"
  );
  const hasValidationDone = terminal.some(
    (event) =>
      (event.step === "VALIDATE_RESULT" || event.step === "VALIDATE_DISCOVERY") &&
      normalizeStatus(event.status) === "completed"
  );
  if (hasPipelineDone || hasValidationDone) return "completed";
  if (terminal.length > 0) return "partial";
  if (events.some((event) => normalizeStatus(event.status) === "started")) return "running";
  return "unknown";
}

export function deriveActiveProgress(events: ProcessingEventSummary[]): {
  module: string;
  stage: string;
  step: string;
  eventType: string;
  message: string | null;
} | null {
  if (!events.length) return null;
  const flowStatus = deriveFlowStatus(events, []);
  if (flowStatus !== "running") return null;

  const terminalKeys = new Set(
    events
      .filter((event) => TERMINAL_STATUSES.has(normalizeStatus(event.status)))
      .map((event) => stepKey(event.module, event.step)),
  );

  const sorted = [...events].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  for (const event of sorted) {
    if (normalizeStatus(event.status) !== "started") continue;
    if (!terminalKeys.has(stepKey(event.module, event.step))) {
      return {
        module: event.module,
        stage: event.stage,
        step: event.step,
        eventType: event.event_type,
        message: event.message ?? null,
      };
    }
  }

  const latest = sorted[0];
  if (!latest) return null;
  return {
    module: latest.module,
    stage: latest.stage,
    step: latest.step,
    eventType: latest.event_type,
    message: latest.message ?? null,
  };
}

export type FlowProgressDetail = {
  percent: number;
  completedSteps: number;
  totalSteps: number;
  batchDone: number | null;
  batchTotal: number | null;
  remainingSteps: Array<{ module: string; step: string }>;
};

export type FlowProgressOptions = {
  /** Kalibráció: korábbi futások eseményei (pl. teljes KB lista). */
  referenceEvents?: ProcessingEventSummary[];
  /** Aktuális dokumentum azonosító — kizárás a referencia futásból. */
  currentItemId?: string | null;
  /** Aktív lépés időinterpolációjához. */
  nowMs?: number;
};

const DEFAULT_STEP_WEIGHT_MS = 1000;
const MIN_STEP_WEIGHT_MS = 100;

/** Időt nagyságrendre kerekít (zajcsökkentés, stabil súlyozás). */
export function roundDurationToMagnitude(durationMs: number): number {
  if (!Number.isFinite(durationMs) || durationMs <= 0) return DEFAULT_STEP_WEIGHT_MS;
  const ms = Math.max(MIN_STEP_WEIGHT_MS, durationMs);
  const exponent = Math.floor(Math.log10(ms));
  const base = 10 ** exponent;
  const normalized = ms / base;
  let factor = 1;
  if (normalized >= 7.5) factor = 10;
  else if (normalized >= 3) factor = 5;
  else if (normalized >= 1.6) factor = 2.5;
  return Math.round(factor * base);
}

/** Utolsó teljesen indexelt futás training_item azonosítója. */
export function findLastCompletedRunItemId(
  events: ProcessingEventSummary[],
  excludeItemId?: string | null,
): string | null {
  const byItem = new Map<string, ProcessingEventSummary[]>();
  for (const event of events) {
    const itemId = resolveFlowItemId(event);
    if (!itemId) continue;
    const bucket = byItem.get(itemId) ?? [];
    bucket.push(event);
    byItem.set(itemId, bucket);
  }

  let bestItemId: string | null = null;
  let bestTime = 0;
  for (const [itemId, itemEvents] of byItem) {
    if (excludeItemId && itemId === excludeItemId) continue;
    const indexingDone = itemEvents.find(
      (event) =>
        event.module === "kb_indexing" &&
        event.step === "PIPELINE" &&
        normalizeStatus(event.status) === "completed",
    );
    if (!indexingDone) continue;
    const time = Date.parse(indexingDone.created_at);
    if (time > bestTime) {
      bestTime = time;
      bestItemId = itemId;
    }
  }
  return bestItemId;
}

export function extractRawStepDurationsMs(
  events: ProcessingEventSummary[],
  understandingSteps: UnderstandingStepSummary[] = [],
): Map<string, number> {
  const raw = new Map<string, number>();
  for (const row of mergeUnderstandingSteps(buildStepRows(events), understandingSteps)) {
    if (normalizeStatus(row.status) !== "completed") continue;
    if (row.durationMs == null || row.durationMs <= 0) continue;
    raw.set(row.key, row.durationMs);
  }
  return raw;
}

/** Modul szintű várható idő: al-lépések duration_ms összege (PIPELINE összesítő külön). */
export function computeModuleWallTimes(
  events: ProcessingEventSummary[],
  rawDurations: Map<string, number> = new Map(),
): Map<string, number> {
  const result = new Map<string, number>();

  for (const moduleName of PIPELINE_MODULE_ORDER) {
    const subKeys = PROCESSING_PIPELINE_CATALOG.filter(
      (entry) => entry.module === moduleName && entry.step !== "PIPELINE",
    ).map((entry) => stepKey(entry.module, entry.step));
    const subSum = subKeys.reduce((sum, key) => sum + (rawDurations.get(key) ?? 0), 0);
    const pipelineMs = rawDurations.get(stepKey(moduleName, "PIPELINE")) ?? 0;

    if (subSum > 0) {
      result.set(moduleName, subSum);
      continue;
    }
    if (pipelineMs > 0) {
      result.set(moduleName, pipelineMs);
      continue;
    }

    const itemId = events.length ? resolveFlowItemId(events[0]) : null;
    const modEvents = events.filter(
      (event) =>
        event.module === moduleName && (!itemId || resolveFlowItemId(event) === itemId),
    );
    if (modEvents.length < 2) continue;
    const parsed = modEvents
      .map((event) => Date.parse(event.created_at))
      .filter((value) => Number.isFinite(value));
    if (parsed.length < 2) continue;
    const wallMs = Math.max(...parsed) - Math.min(...parsed);
    if (wallMs > 0) result.set(moduleName, wallMs);
  }

  return result;
}

function normalizeModuleStepWeights(
  profile: Map<string, number>,
  rawDurations: Map<string, number>,
  moduleWallTimes: Map<string, number>,
): void {
  for (const moduleName of PIPELINE_MODULE_ORDER) {
    const entries = PROCESSING_PIPELINE_CATALOG.filter((entry) => entry.module === moduleName);
    if (!entries.length) continue;

    const pipelineKey = stepKey(moduleName, "PIPELINE");
    const subEntries = entries.filter((entry) => entry.step !== "PIPELINE");
    const subKeys = subEntries.map((entry) => stepKey(entry.module, entry.step));
    const rawSubTotal = subKeys.reduce((sum, key) => sum + (rawDurations.get(key) ?? 0), 0);
    const hasSubMeasurements = rawSubTotal > 0;
    const moduleWall = moduleWallTimes.get(moduleName);

    if (hasSubMeasurements) {
      profile.set(pipelineKey, MIN_STEP_WEIGHT_MS);

      for (const key of subKeys) {
        if (!profile.has(key)) profile.set(key, MIN_STEP_WEIGHT_MS);
      }

      const measurableKeys = subKeys.filter((key) => (rawDurations.get(key) ?? 0) > 0);
      const measuredTotal = measurableKeys.reduce((sum, key) => sum + (profile.get(key) ?? 0), 0);
      const targetTotal =
        moduleWall != null && moduleWall > 0 ? roundDurationToMagnitude(moduleWall) : measuredTotal;

      if (measuredTotal > 0 && targetTotal > 0) {
        const scale = targetTotal / measuredTotal;
        for (const key of measurableKeys) {
          profile.set(key, Math.max(MIN_STEP_WEIGHT_MS, roundDurationToMagnitude((profile.get(key) ?? 0) * scale)));
        }
      }
      continue;
    }

    const pipelineRaw = rawDurations.get(pipelineKey) ?? 0;
    if (pipelineRaw > 0) {
      profile.set(pipelineKey, roundDurationToMagnitude(pipelineRaw));
      for (const key of subKeys) profile.set(key, MIN_STEP_WEIGHT_MS);
      continue;
    }

    if (moduleWall != null && moduleWall > 0) {
      const perStep = Math.max(MIN_STEP_WEIGHT_MS, roundDurationToMagnitude(moduleWall / entries.length));
      for (const entry of entries) {
        profile.set(stepKey(entry.module, entry.step), perStep);
      }
    }
  }
}

/** Lépésenkénti várható idő (ms) az utolsó sikeres futás + aktuális befejezett lépések alapján. */
export function buildStepDurationProfile(
  referenceEvents: ProcessingEventSummary[],
  options?: {
    excludeItemId?: string | null;
    overlayEvents?: ProcessingEventSummary[];
    understandingSteps?: UnderstandingStepSummary[];
  },
): Map<string, number> {
  const profile = new Map<string, number>();
  const rawDurations = new Map<string, number>();

  const lastItemId = findLastCompletedRunItemId(referenceEvents, options?.excludeItemId);
  if (lastItemId) {
    const itemEvents = referenceEvents.filter((event) => resolveFlowItemId(event) === lastItemId);
    for (const [key, value] of extractRawStepDurationsMs(itemEvents)) {
      rawDurations.set(key, value);
      profile.set(key, roundDurationToMagnitude(value));
    }
  }

  if (options?.overlayEvents?.length) {
    for (const [key, value] of extractRawStepDurationsMs(
      options.overlayEvents,
      options.understandingSteps ?? [],
    )) {
      rawDurations.set(key, value);
      profile.set(key, roundDurationToMagnitude(value));
    }
  }

  const moduleWallTimes = computeModuleWallTimes(
    options?.overlayEvents?.length
      ? options.overlayEvents
      : lastItemId
        ? referenceEvents.filter((event) => resolveFlowItemId(event) === lastItemId)
        : referenceEvents,
    rawDurations,
  );
  normalizeModuleStepWeights(profile, rawDurations, moduleWallTimes);

  for (const entry of PROCESSING_PIPELINE_CATALOG) {
    const key = stepKey(entry.module, entry.step);
    if (!profile.has(key)) profile.set(key, MIN_STEP_WEIGHT_MS);
  }

  return profile;
}

function findStepStartedAt(events: ProcessingEventSummary[], module: string, step: string): number | null {
  const matches = events
    .filter(
      (event) =>
        event.module === module &&
        event.step === step &&
        normalizeStatus(event.status) === "started",
    )
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const latest = matches[0];
  if (!latest) return null;
  const parsed = Date.parse(latest.created_at);
  return Number.isFinite(parsed) ? parsed : null;
}

export function computeWeightedProgressPercent(
  timeline: ProcessingStepRow[],
  weights: number[],
  events: ProcessingEventSummary[],
  nowMs?: number,
): number {
  if (!timeline.length) return 0;

  let earnedWeight = 0;
  let activeIndex = -1;

  for (let index = 0; index < timeline.length; index += 1) {
    const row = timeline[index];
    const status = normalizeStatus(row.status);
    if (status === "completed") {
      earnedWeight += weights[index] ?? DEFAULT_STEP_WEIGHT_MS;
      continue;
    }
    if (status === "started" || status === "failed" || status === "skipped") {
      activeIndex = index;
      break;
    }
    if (row.isPending || status === "pending") {
      activeIndex = index;
      break;
    }
  }

  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  if (totalWeight <= 0) return 0;

  if (activeIndex >= 0) {
    const stepWeight = weights[activeIndex] ?? DEFAULT_STEP_WEIGHT_MS;
    const row = timeline[activeIndex];
    let ratio = 0.04;

    const batch = extractBatchProgress(events);
    if (batch && batch.total > 0) {
      ratio = Math.min(0.95, batch.done / batch.total);
    } else if (nowMs != null) {
      const startedAt = findStepStartedAt(events, row.module, row.step);
      if (startedAt != null) {
        ratio = Math.min(0.92, Math.max(0, nowMs - startedAt) / Math.max(stepWeight, MIN_STEP_WEIGHT_MS));
      }
    }

    earnedWeight += stepWeight * ratio;
  }

  return Math.round((earnedWeight / totalWeight) * 100);
}

function readPositiveInt(value: unknown): number | null {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num) || num < 0) return null;
  return Math.floor(num);
}

/** Aktív lépés batch előrehaladása (embedding, indexelés, Qdrant ellenőrzés). */
export function extractBatchProgress(events: ProcessingEventSummary[]): { done: number; total: number } | null {
  const sorted = [...events].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  for (const event of sorted) {
    const out = event.output_summary_json ?? {};
    const expected = readPositiveInt(out.expected_points);
    const verified = readPositiveInt(out.verified_points);
    if (expected != null && verified != null && expected > 0) {
      return { done: verified, total: expected };
    }
    const indexed = readPositiveInt(out.indexed);
    const points = readPositiveInt(out.points);
    if (indexed != null && points != null && points > 0) {
      return { done: indexed, total: points };
    }
    const generated = readPositiveInt(out.generated);
    if (generated != null) {
      const failed = readPositiveInt(out.failed) ?? 0;
      const total = generated + failed;
      if (total > 0) return { done: generated, total };
    }
    const chunksIndexed = readPositiveInt(out.chunks_indexed);
    const chunksTotal = readPositiveInt(out.chunks_total);
    if (chunksIndexed != null && chunksTotal != null && chunksTotal > 0) {
      return { done: chunksIndexed, total: chunksTotal };
    }
  }
  return null;
}

export function deriveFlowProgress(
  events: ProcessingEventSummary[],
  issues: ProcessingIssueSummary[],
  understandingSteps: UnderstandingStepSummary[] = [],
  options: FlowProgressOptions = {},
): FlowProgressDetail | null {
  const flowStatus = deriveFlowStatus(events, issues);
  if (flowStatus !== "running") return null;

  const progressTimeline = buildPipelineTimeline(events, understandingSteps);
  const displayTimeline = buildPipelineTimelineCompact(events, understandingSteps);
  const completedSteps = progressTimeline.filter((row) => normalizeStatus(row.status) === "completed").length;
  const totalSteps = progressTimeline.length;
  const pendingRows = displayTimeline.filter(
    (row) => row.isPending || normalizeStatus(row.status) === "pending" || normalizeStatus(row.status) === "started",
  );
  const remainingSteps = pendingRows.slice(0, 4).map((row) => ({ module: row.module, step: row.step }));

  const currentItemId =
    options.currentItemId ?? (events.length ? resolveFlowItemId(events[0]) : null);
  const referenceEvents = options.referenceEvents ?? events;
  const durationProfile = buildStepDurationProfile(referenceEvents, {
    excludeItemId: currentItemId,
    overlayEvents: events,
    understandingSteps,
  });
  const weights = progressTimeline.map((row) => durationProfile.get(row.key) ?? DEFAULT_STEP_WEIGHT_MS);

  const percent = computeWeightedProgressPercent(progressTimeline, weights, events, options.nowMs);
  const batch = extractBatchProgress(events);

  return {
    percent: Math.min(Math.max(percent, completedSteps > 0 ? 1 : 0), 99),
    completedSteps,
    totalSteps,
    batchDone: batch?.done ?? null,
    batchTotal: batch?.total ?? null,
    remainingSteps,
  };
}

export type FlowProcessingDisplay = {
  badgeStatus: string;
  flowStatus: ProcessingFlowStatus;
  module: string | null;
  step: string | null;
  stage: string | null;
  source: "events" | "job";
  jobStatus: string | null;
};

function findPipelineHead(events: ProcessingEventSummary[]): {
  module: string;
  step: string;
  stage: string;
} | null {
  for (const moduleName of [...PIPELINE_MODULE_ORDER].reverse()) {
    const pipelineDone = events.some(
      (event) =>
        event.module === moduleName &&
        event.step === "PIPELINE" &&
        normalizeStatus(event.status) === "completed",
    );
    if (pipelineDone) {
      const match = events.find(
        (event) => event.module === moduleName && event.step === "PIPELINE",
      );
      return {
        module: moduleName,
        step: "PIPELINE",
        stage: match?.stage ?? moduleName,
      };
    }
  }

  const sorted = [...events].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const latest = sorted.find((event) => normalizeStatus(event.status) !== "pending");
  if (!latest) return null;
  return {
    module: latest.module,
    step: latest.step,
    stage: latest.stage,
  };
}

function jobStatusFallbackPosition(jobStatus: string | null | undefined): {
  badgeStatus: string;
  flowStatus: ProcessingFlowStatus;
  module: string | null;
  step: string | null;
  stage: string | null;
} {
  const status = String(jobStatus ?? "").trim().toLowerCase();
  if (!status) {
    return { badgeStatus: "unknown", flowStatus: "unknown", module: null, step: null, stage: null };
  }
  if (status === "failed" || status === "retryable") {
    return {
      badgeStatus: "failed",
      flowStatus: "failed",
      module: "kb_understanding",
      step: "PIPELINE",
      stage: "UNDERSTANDING",
    };
  }
  if (status === "ready_for_discovery") {
    return {
      badgeStatus: "running",
      flowStatus: "running",
      module: "kb_discovery",
      step: "DETECT_LANGUAGE",
      stage: "LANGUAGE_DETECTION",
    };
  }
  if (["queued", "extracting", "normalizing", "chunking", "validating"].includes(status)) {
    const stepMap: Record<string, string> = {
      extracting: "EXTRACT_CONTENT",
      normalizing: "NORMALIZE_PARTS",
      chunking: "BUILD_CHUNKS",
      validating: "VALIDATE_RESULT",
      queued: "EXTRACT_CONTENT",
    };
    return {
      badgeStatus: "running",
      flowStatus: "running",
      module: "kb_understanding",
      step: stepMap[status] ?? "PIPELINE",
      stage: status.toUpperCase(),
    };
  }
  if (status === "partial") {
    return {
      badgeStatus: "partial",
      flowStatus: "partial",
      module: "kb_understanding",
      step: "PIPELINE",
      stage: "UNDERSTANDING",
    };
  }
  return {
    badgeStatus: "unknown",
    flowStatus: "unknown",
    module: "kb_understanding",
    step: "PIPELINE",
    stage: "UNDERSTANDING",
  };
}

/** Összesített feldolgozási állapot: pipeline flow + aktuális modul/ lépés (nem csak understanding job). */
export function deriveFlowProcessingDisplay(
  events: ProcessingEventSummary[],
  issues: ProcessingIssueSummary[],
  jobStatus?: string | null,
): FlowProcessingDisplay {
  if (events.length) {
    const flowStatus = deriveFlowStatus(events, issues);
    const active = deriveActiveProgress(events);
    if (active) {
      return {
        badgeStatus: "running",
        flowStatus,
        module: active.module,
        step: active.step,
        stage: active.stage,
        source: "events",
        jobStatus: jobStatus ?? null,
      };
    }

    const head = findPipelineHead(events);
    const failedEvent = [...events]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .find((event) => normalizeStatus(event.status) === "failed");

    if (flowStatus === "failed" && failedEvent) {
      return {
        badgeStatus: "failed",
        flowStatus,
        module: failedEvent.module,
        step: failedEvent.step,
        stage: failedEvent.stage,
        source: "events",
        jobStatus: jobStatus ?? null,
      };
    }

    const indexingComplete = events.some(
      (event) =>
        event.module === "kb_indexing" &&
        event.step === "PIPELINE" &&
        normalizeStatus(event.status) === "completed",
    );
    if (indexingComplete) {
      return {
        badgeStatus: "completed",
        flowStatus: "completed",
        module: "kb_indexing",
        step: "PIPELINE",
        stage: head?.stage ?? "INDEXING",
        source: "events",
        jobStatus: jobStatus ?? null,
      };
    }

    return {
      badgeStatus: flowStatus,
      flowStatus,
      module: head?.module ?? null,
      step: head?.step ?? null,
      stage: head?.stage ?? null,
      source: "events",
      jobStatus: jobStatus ?? null,
    };
  }

  const fallback = jobStatusFallbackPosition(jobStatus);
  return {
    ...fallback,
    source: "job",
    jobStatus: jobStatus ?? null,
  };
}

export function buildFlowSummaries(
  runs: IngestRun[],
  events: ProcessingEventSummary[],
  issues: ProcessingIssueSummary[],
  options: Pick<FlowProgressOptions, "nowMs"> = {},
): ProcessingFlowSummary[] {
  const catalog = buildItemCatalogFromRuns(runs);
  enrichCatalogFromEvents(catalog, events);
  const eventsByItem = new Map<string, ProcessingEventSummary[]>();
  const issuesByItem = new Map<string, ProcessingIssueSummary[]>();

  for (const event of events) {
    const itemId = resolveFlowItemId(event);
    if (!itemId) continue;
    const bucket = eventsByItem.get(itemId) ?? [];
    bucket.push(event);
    eventsByItem.set(itemId, bucket);
  }

  for (const issue of issues) {
    const itemId = resolveFlowItemId(issue);
    if (!itemId) continue;
    const bucket = issuesByItem.get(itemId) ?? [];
    bucket.push(issue);
    issuesByItem.set(itemId, bucket);
  }

  const itemIds = new Set<string>([...catalog.keys(), ...eventsByItem.keys()]);
  const flows: ProcessingFlowSummary[] = [];

  for (const itemId of itemIds) {
    const meta = catalog.get(itemId);
    const itemEvents = eventsByItem.get(itemId) ?? [];
    const itemIssues = issuesByItem.get(itemId) ?? [];
    const stepRows = buildStepRows(itemEvents);
    const lastEvent = itemEvents[0] ?? null;
    const active = deriveActiveProgress(itemEvents);
    const pipelineHead = active ? null : findPipelineHead(itemEvents);
    const progress = deriveFlowProgress(itemEvents, itemIssues, [], {
      referenceEvents: events,
      currentItemId: itemId,
      nowMs: options.nowMs,
    });
    flows.push({
      itemId,
      title: meta?.title ?? itemId,
      inputType: meta?.inputType ?? "unknown",
      charCount: meta?.charCount ?? null,
      lastEventAt: lastEvent?.created_at ?? null,
      status: deriveFlowStatus(itemEvents, itemIssues),
      completedSteps: progress?.completedSteps ?? stepRows.filter((row) => normalizeStatus(row.status) === "completed").length,
      failedSteps: stepRows.filter((row) => normalizeStatus(row.status) === "failed").length,
      openIssues: countOpenBlockingIssues(itemIssues),
      latestMessage: active?.message ?? lastEvent?.message ?? itemIssues[0]?.issue_message ?? null,
      activeModule: active?.module ?? pipelineHead?.module ?? null,
      activeStage: active?.stage ?? pipelineHead?.stage ?? null,
      activeStep: active?.step ?? pipelineHead?.step ?? null,
      activeEventType: active?.eventType ?? null,
      progressPercent: progress?.percent ?? null,
      progressTotalSteps: progress?.totalSteps ?? null,
      progressBatchDone: progress?.batchDone ?? null,
      progressBatchTotal: progress?.batchTotal ?? null,
    });
  }

  return flows.sort((a, b) => {
    const aTime = a.lastEventAt ? Date.parse(a.lastEventAt) : 0;
    const bTime = b.lastEventAt ? Date.parse(b.lastEventAt) : 0;
    return bTime - aTime;
  });
}

function normalizeIssueToken(value: string | null | undefined): string {
  return String(value ?? "").trim().toLowerCase().replace(/_/g, "");
}

/** Nyitott issue illesztése pipeline lépés sorhoz (modul + stage/step). */
export function issueMatchesStep(
  issue: ProcessingIssueSummary,
  step: ProcessingStepRow,
): boolean {
  if (issue.module !== step.module) return false;

  const issueStep = normalizeIssueToken(issue.step);
  const issueStage = normalizeIssueToken(issue.stage);
  const stepStep = normalizeIssueToken(step.step);
  const stepStage = normalizeIssueToken(step.stage);

  if (issueStep && issueStep === stepStep) return true;
  if (issueStep === "enrichment" && stepStep === "enrichlocal") return true;
  if (issueStage && issueStage === stepStage) return true;
  if (issueStage.includes("enrichment") && stepStep === "enrichlocal") return true;
  if (step.step === "PIPELINE" && issueStep === "pipeline") return true;
  return false;
}

export function getOpenIssuesForStep(
  issues: ProcessingIssueSummary[],
  step: ProcessingStepRow,
): ProcessingIssueSummary[] {
  return issues.filter((issue) => issue.status === "OPEN" && issueMatchesStep(issue, step));
}

export function buildStepRows(events: ProcessingEventSummary[]): ProcessingStepRow[] {
  const latestByKey = new Map<string, ProcessingEventSummary>();
  for (const event of [...events].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))) {
    const key = stepKey(event.module, event.step);
    const status = normalizeStatus(event.status);
    const current = latestByKey.get(key);
    if (TERMINAL_STATUSES.has(status)) {
      latestByKey.set(key, event);
      continue;
    }
    if (status === "started" && (!current || normalizeStatus(current.status) === "started")) {
      latestByKey.set(key, event);
    }
  }
  return [...latestByKey.values()]
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .map((event) => ({
      key: stepKey(event.module, event.step),
      module: event.module,
      stage: event.stage,
      step: event.step,
      status: normalizeStatus(event.status),
      durationMs: event.duration_ms ?? null,
      createdAt: event.created_at,
      message: event.message ?? null,
      errorCode: typeof event.metadata_json?.error_code === "string" ? event.metadata_json.error_code : null,
      inputSummary: event.input_summary_json ?? {},
      outputSummary: event.output_summary_json ?? {},
      eventType: event.event_type,
      isPending: false,
      catalogOrder: PROCESSING_PIPELINE_CATALOG.findIndex(
        (entry) => entry.module === event.module && entry.step === event.step,
      ),
    }));
}

/** Események + katalógus: teljes pipeline sorrend, hiányzó lépések „pending” státusszal. */
export function buildPipelineTimeline(
  events: ProcessingEventSummary[],
  understandingSteps: UnderstandingStepSummary[] = [],
): ProcessingStepRow[] {
  const actualRows = mergeUnderstandingSteps(buildStepRows(events), understandingSteps);
  const actualMap = new Map(actualRows.map((row) => [row.key, row]));

  const timeline: ProcessingStepRow[] = [];
  const seenKeys = new Set<string>();

  for (let index = 0; index < PROCESSING_PIPELINE_CATALOG.length; index += 1) {
    const entry = PROCESSING_PIPELINE_CATALOG[index];
    const key = stepKey(entry.module, entry.step);
    seenKeys.add(key);
    const existing = actualMap.get(key);
    if (existing) {
      timeline.push({ ...existing, catalogOrder: index, isPending: false });
    } else {
      timeline.push(emptyPendingRow(entry, index));
    }
  }

  for (const row of actualRows) {
    if (!seenKeys.has(row.key)) {
      timeline.push({
        ...row,
        catalogOrder: row.catalogOrder >= 0 ? row.catalogOrder : PROCESSING_PIPELINE_CATALOG.length + timeline.length,
        isPending: false,
      });
    }
  }

  return timeline.sort((a, b) => a.catalogOrder - b.catalogOrder);
}

/** Csak már elkezdett vagy befejezett modulok + a következő folyamatban lévő modul pending lépései. */
export function buildPipelineTimelineCompact(
  events: ProcessingEventSummary[],
  understandingSteps: UnderstandingStepSummary[] = [],
): ProcessingStepRow[] {
  const full = buildPipelineTimeline(events, understandingSteps);
  const flowStatus = deriveFlowStatus(events, []);
  if (flowStatus === "completed") {
    return full.filter((row) => !row.isPending);
  }

  let lastActiveIndex = -1;
  for (let index = 0; index < full.length; index += 1) {
    if (!full[index].isPending) {
      lastActiveIndex = index;
    }
  }

  if (lastActiveIndex < 0) {
    return full.filter((row, index) => {
      if (!row.isPending) return true;
      return index < PROCESSING_PIPELINE_CATALOG.length && row.module === PROCESSING_PIPELINE_CATALOG[0].module;
    });
  }

  const activeModule = full[lastActiveIndex]?.module;
  const moduleOrder = [
    "kb_understanding",
    "kb_discovery",
    "kb_embedding",
    "kb_indexing",
  ];
  const activeModuleIndex = moduleOrder.indexOf(activeModule);
  const visibleModules = new Set(
    moduleOrder.slice(0, activeModuleIndex + 1 + (flowStatus === "running" ? 1 : 0)),
  );

  return full.filter((row) => visibleModules.has(row.module));
}

export function findStepRow(events: ProcessingEventSummary[], module: string, step: string): ProcessingStepRow | null {
  return buildStepRows(events).find((row) => row.module === module && row.step === step) ?? null;
}

export function mergeUnderstandingSteps(stepRows: ProcessingStepRow[], understandingSteps: UnderstandingStepSummary[]): ProcessingStepRow[] {
  if (!understandingSteps.length) return stepRows;
  const merged = [...stepRows];
  for (const step of understandingSteps) {
    const key = stepKey("kb_understanding", step.step);
    if (merged.some((row) => row.key === key)) continue;
    merged.push({
      key,
      module: "kb_understanding",
      stage: step.step,
      step: step.step,
      status: normalizeStatus(step.status),
      durationMs: step.duration_ms ?? null,
      createdAt: step.created_at ?? new Date(0).toISOString(),
      message: step.error_message ?? null,
      errorCode: step.error_code ?? null,
      inputSummary: step.input_summary ?? {},
      outputSummary: step.output_summary ?? {},
      eventType: "UNDERSTANDING_STEP",
      isPending: false,
      catalogOrder: PROCESSING_PIPELINE_CATALOG.findIndex(
        (entry) => entry.module === "kb_understanding" && entry.step === step.step,
      ),
    });
  }
  return merged.sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt));
}

export type FlatSummaryRow = {
  key: string;
  labelKey: string;
  value: string;
  group: "input" | "output" | "meta";
};

export function flattenSummary(
  summary: Record<string, unknown>,
  group: FlatSummaryRow["group"],
  prefix = ""
): FlatSummaryRow[] {
  const rows: FlatSummaryRow[] = [];
  for (const [rawKey, rawValue] of Object.entries(summary)) {
    const key = prefix ? `${prefix}.${rawKey}` : rawKey;
    if (rawValue === null || rawValue === undefined) continue;
    if (Array.isArray(rawValue)) {
      if (rawValue.every((item) => typeof item !== "object")) {
        rows.push({
          key,
          labelKey: key,
          value: rawValue.map(String).join(", "),
          group,
        });
        continue;
      }
      rows.push({
        key,
        labelKey: key,
        value: JSON.stringify(rawValue, null, 2),
        group,
      });
      continue;
    }
    if (typeof rawValue === "object") {
      rows.push(...flattenSummary(rawValue as Record<string, unknown>, group, key));
      continue;
    }
    rows.push({
      key,
      labelKey: key,
      value: String(rawValue),
      group,
    });
  }
  return rows;
}

export function formatDurationMs(durationMs: number | null | undefined, t: (key: string) => string): string {
  if (durationMs == null || !Number.isFinite(durationMs)) return "—";
  if (durationMs < 1000) return `${durationMs} ${t("kb.processingMonitor.units.ms")}`;
  const seconds = (durationMs / 1000).toFixed(durationMs >= 10_000 ? 0 : 1);
  return `${seconds} ${t("kb.processingMonitor.units.sec")}`;
}

const MONITOR_PREFIX = "kb.processingMonitor";

type ProcessingMonitorLabelKind =
  | "module"
  | "stage"
  | "step"
  | "issue"
  | "event"
  | "jobStatus"
  | "flowStatus"
  | "status"
  | "inputType"
  | "severity"
  | "stepOrStage"
  | "entityType"
  | "mentionType";

function prefixesForKind(kind: ProcessingMonitorLabelKind): string[] {
  switch (kind) {
    case "module":
      return [`${MONITOR_PREFIX}.modules`];
    case "stage":
      return [`${MONITOR_PREFIX}.stages`];
    case "step":
      return [`${MONITOR_PREFIX}.steps`];
    case "issue":
      return [`${MONITOR_PREFIX}.issueCodes`];
    case "event":
      return [`${MONITOR_PREFIX}.eventTypes`];
    case "jobStatus":
      return [`${MONITOR_PREFIX}.jobStatuses`];
    case "flowStatus":
      return [`${MONITOR_PREFIX}.flowStatuses`];
    case "status":
      return [`${MONITOR_PREFIX}.statuses`];
    case "inputType":
      return [`${MONITOR_PREFIX}.inputTypes`];
    case "severity":
      return [`${MONITOR_PREFIX}.severities`];
    case "entityType":
      return [`${MONITOR_PREFIX}.entityTypes`];
    case "mentionType":
      return [`${MONITOR_PREFIX}.mentionTypes`];
    case "stepOrStage":
      return [
        `${MONITOR_PREFIX}.steps`,
        `${MONITOR_PREFIX}.stages`,
        `${MONITOR_PREFIX}.eventTypes`,
      ];
    default:
      return [];
  }
}

/** Fordított címke a monitorban; ismeretlen kulcs esetén olvasható fallback. */
export function translateProcessingMonitorKey(
  t: (key: string) => string,
  value: string | null | undefined,
  kind: ProcessingMonitorLabelKind,
): string {
  if (!value) return "";
  for (const prefix of prefixesForKind(kind)) {
    const key = `${prefix}.${value}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return value.replace(/_/g, " ");
}
