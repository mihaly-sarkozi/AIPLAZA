import type { IngestItem, IngestRun } from "../../../api/services/kb/types";
import type {
  ProcessingEventSummary,
  ProcessingIssueSummary,
  UnderstandingStepSummary,
} from "../../../api/services/kb/kbProcessingApi";

export type ProcessingFlowStatus = "completed" | "failed" | "running" | "partial" | "unknown";

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
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "skipped"]);

function normalizeStatus(status: string | null | undefined): string {
  return String(status ?? "").trim().toLowerCase();
}

function stepKey(module: string, step: string): string {
  return `${module}::${step}`;
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

export function deriveFlowStatus(events: ProcessingEventSummary[], issues: ProcessingIssueSummary[]): ProcessingFlowStatus {
  const terminal = events.filter((event) => TERMINAL_STATUSES.has(normalizeStatus(event.status)));
  if (terminal.some((event) => normalizeStatus(event.status) === "failed")) return "failed";
  const openIssues = issues.filter((issue) => issue.status === "OPEN");
  if (openIssues.some((issue) => ["ERROR", "CRITICAL"].includes(issue.severity))) return "failed";
  if (openIssues.length > 0) return "partial";
  const hasIndexingDone = terminal.some(
    (event) =>
      event.module === "kb_indexing" &&
      event.step === "PIPELINE" &&
      normalizeStatus(event.status) === "completed"
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

export function buildFlowSummaries(
  runs: IngestRun[],
  events: ProcessingEventSummary[],
  issues: ProcessingIssueSummary[]
): ProcessingFlowSummary[] {
  const catalog = buildItemCatalogFromRuns(runs);
  const eventsByItem = new Map<string, ProcessingEventSummary[]>();
  const issuesByItem = new Map<string, ProcessingIssueSummary[]>();

  for (const event of events) {
    const itemId = event.training_item_id;
    if (!itemId) continue;
    const bucket = eventsByItem.get(itemId) ?? [];
    bucket.push(event);
    eventsByItem.set(itemId, bucket);
  }

  for (const issue of issues) {
    const itemId = issue.training_item_id;
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
    flows.push({
      itemId,
      title: meta?.title ?? itemId,
      inputType: meta?.inputType ?? "unknown",
      charCount: meta?.charCount ?? null,
      lastEventAt: lastEvent?.created_at ?? null,
      status: deriveFlowStatus(itemEvents, itemIssues),
      completedSteps: stepRows.filter((row) => normalizeStatus(row.status) === "completed").length,
      failedSteps: stepRows.filter((row) => normalizeStatus(row.status) === "failed").length,
      openIssues: itemIssues.filter((issue) => issue.status === "OPEN").length,
      latestMessage: lastEvent?.message ?? itemIssues[0]?.issue_message ?? null,
    });
  }

  return flows.sort((a, b) => {
    const aTime = a.lastEventAt ? Date.parse(a.lastEventAt) : 0;
    const bTime = b.lastEventAt ? Date.parse(b.lastEventAt) : 0;
    return bTime - aTime;
  });
}

export function buildStepRows(events: ProcessingEventSummary[]): ProcessingStepRow[] {
  const latestByKey = new Map<string, ProcessingEventSummary>();
  for (const event of [...events].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))) {
    if (!TERMINAL_STATUSES.has(normalizeStatus(event.status))) continue;
    latestByKey.set(stepKey(event.module, event.step), event);
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
    }));
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
  | "stepOrStage";

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
