import type { IngestItem, IngestRun } from "../services";

export const ACTIVE_RUN_STATUSES = new Set(["received", "queued", "processing"]);

export type TrainingLogRow = {
  runId: string;
  itemId: string | null;
  status: string;
  timestamp: string;
  kindLabel: string;
  title: string;
  preview: string;
};

export type ProcessingModuleSummary = {
  key?: string;
  status?: string;
  label?: string;
  processed_parts?: number | null;
  total_parts?: number | null;
  progress_percent?: number | null;
  message?: string | null;
  error_message?: string | null;
  run_id?: string | null;
};

export type DocumentProgressSummary = {
  phase?: string;
  processed_parts?: number | null;
  total_parts?: number | null;
  progress_percent?: number | null;
  label?: string | null;
};

export type ItemProcessingSummary = {
  overall_status?: string;
  modules: Record<string, ProcessingModuleSummary>;
  document_progress?: DocumentProgressSummary | null;
};

export type RunProgressSummary = {
  total_items?: number;
  terminal_items?: number;
  overall_percent?: number;
  active_item_id?: string | null;
  active_item_label?: string | null;
  active_item_status?: string | null;
  active_module?: string | null;
  active_module_label?: string | null;
  active_message?: string | null;
  stopped_at?: string | null;
  last_error_message?: string | null;
};

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("hu-HU");
}

export function getStatusLabel(status: string): string {
  switch ((status || "").trim()) {
    case "received":
      return "Fogadva";
    case "queued":
      return "Sorban";
    case "processing":
      return "Feldolgozás";
    case "completed":
      return "Kész";
    case "failed":
      return "Hiba";
    case "duplicate":
      return "Duplikált";
    case "rejected":
      return "Elutasítva";
    case "validated":
      return "Validálva";
    default:
      return status || "Ismeretlen";
  }
}

export function getModuleStatusLabel(status: string | null | undefined): string {
  switch ((status || "").trim()) {
    case "queued":
      return "Várakozik";
    case "processing":
      return "Folyamatban";
    case "completed":
      return "Kész";
    case "failed":
      return "Hibás";
    case "skipped":
      return "Kihagyva";
    default:
      return status || "Ismeretlen";
  }
}

export function getStatusBadgeClass(status: string): string {
  switch ((status || "").trim()) {
    case "completed":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "failed":
    case "rejected":
      return "bg-rose-500/10 text-rose-700 dark:text-rose-300";
    case "duplicate":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "processing":
      return "bg-blue-500/10 text-blue-700 dark:text-blue-300";
    case "queued":
    case "received":
    case "validated":
      return "bg-slate-500/10 text-slate-700 dark:text-slate-300";
    default:
      return "bg-slate-500/10 text-slate-700 dark:text-slate-300";
  }
}

export function getItemKindLabel(item: Pick<IngestItem, "input_type"> | null | undefined): string {
  switch ((item?.input_type || "").trim()) {
    case "file":
      return "Fájl";
    case "text":
      return "Szöveg";
    case "url":
      return "Hivatkozás";
    default:
      return item?.input_type || "Ismeretlen";
  }
}

export function getItemTitle(item: IngestItem): string {
  if (item.input_type === "file") {
    return item.display_name || item.title || "Ismeretlen fájl";
  }
  if (item.input_type === "url") {
    const url = typeof item.metadata?.url === "string" ? item.metadata.url : item.origin || item.display_name || item.title || "";
    return truncate(normalizeWhitespace(url), 15);
  }

  const textPreview =
    typeof item.metadata?.text_preview === "string"
      ? item.metadata.text_preview
      : item.display_name || item.title || "Szöveg";
  return truncate(normalizeWhitespace(textPreview), 15);
}

export function getItemPreview(item: IngestItem): string {
  if (item.input_type === "file") {
    return item.display_name || item.title || "Ismeretlen fájl";
  }
  if (item.input_type === "url") {
    const url = typeof item.metadata?.url === "string" ? item.metadata.url : item.origin;
    return truncate(normalizeWhitespace(url || item.display_name || item.title || ""), 160);
  }

  const textPreview =
    typeof item.metadata?.text_preview === "string"
      ? item.metadata.text_preview
      : item.display_name || item.title || "";
  return truncate(normalizeWhitespace(textPreview), 160);
}

export function getItemProcessingSummary(item: IngestItem | null | undefined): ItemProcessingSummary {
  const raw = item?.metadata?.processing_summary;
  if (!raw || typeof raw !== "object") {
    return { modules: {}, document_progress: null };
  }
  const summary = raw as Record<string, unknown>;
  const rawModules = summary.modules;
  const modules =
    rawModules && typeof rawModules === "object" ? (rawModules as Record<string, ProcessingModuleSummary>) : {};
  const documentProgress =
    summary.document_progress && typeof summary.document_progress === "object"
      ? (summary.document_progress as DocumentProgressSummary)
      : null;
  return {
    overall_status: typeof summary.overall_status === "string" ? summary.overall_status : undefined,
    modules,
    document_progress: documentProgress,
  };
}

export function getRunProgressSummary(run: IngestRun | null | undefined): RunProgressSummary {
  const raw = run?.metadata?.progress_summary;
  if (!raw || typeof raw !== "object") {
    return {};
  }
  return raw as RunProgressSummary;
}

export function getRunProgressPercent(run: IngestRun | null | undefined): number {
  const summary = getRunProgressSummary(run);
  if (typeof summary.overall_percent === "number") {
    return Math.max(0, Math.min(100, Math.round(summary.overall_percent)));
  }
  if (!run) return 0;
  if (run.status === "completed") return 100;
  const total = Math.max(run.batch_size || 0, 1);
  const done = run.completed_count + run.failed_count + run.duplicate_count + run.rejected_count;
  return Math.max(0, Math.min(99, Math.round((done / total) * 100)));
}

export function getRunProgressLabel(run: IngestRun | null | undefined): string {
  const summary = getRunProgressSummary(run);
  if (typeof summary.active_message === "string" && summary.active_message.trim()) {
    return summary.active_message;
  }
  if (typeof summary.active_module_label === "string" && summary.active_module_label.trim()) {
    return summary.active_module_label;
  }
  if (typeof summary.stopped_at === "string" && summary.stopped_at.trim()) {
    return `Megállt itt: ${summary.stopped_at}`;
  }
  return getStatusLabel(run?.status || "");
}

export function formatModuleProgress(module: ProcessingModuleSummary | undefined): string {
  if (!module) return "nincs adat";
  const label = getModuleStatusLabel(module.status);
  if (
    typeof module.processed_parts === "number" &&
    typeof module.total_parts === "number" &&
    module.total_parts > 0
  ) {
    const percent =
      typeof module.progress_percent === "number" ? ` (${Math.round(module.progress_percent)}%)` : "";
    return `${label}: ${module.processed_parts}/${module.total_parts}${percent}`;
  }
  return label;
}

export function getItemProcessingPreview(item: IngestItem | null | undefined): string {
  if (!item) return "nincs adat";
  const summary = getItemProcessingSummary(item);
  const parser = summary.modules.parser;
  const interpretation = summary.modules.sentence_interpretation;
  const evaluation = summary.modules.sentence_evaluation;
  const parts = [
    `Parser: ${formatModuleProgress(parser)}`,
    `Értelmezés: ${formatModuleProgress(interpretation)}`,
    `Értékelés: ${formatModuleProgress(evaluation)}`,
  ];
  if (summary.document_progress?.label) {
    parts.push(String(summary.document_progress.label));
  }
  return parts.join(" | ");
}

export function getRunProcessingPreview(run: IngestRun | null | undefined): string {
  if (!run) return "nincs adat";
  const summary = getRunProgressSummary(run);
  const percent = getRunProgressPercent(run);
  const parts = [`${percent}%`];
  const label = getRunProgressLabel(run);
  if (label) parts.push(label);
  if (typeof summary.active_item_label === "string" && summary.active_item_label.trim()) {
    parts.push(summary.active_item_label);
  }
  return parts.join(" | ");
}

export function getRunPrimaryItem(run: IngestRun, preferredItemId?: string | null): IngestItem | null {
  if (preferredItemId) {
    const selected = run.items.find((item) => item.id === preferredItemId);
    if (selected) return selected;
  }
  return run.items[0] ?? null;
}

export function buildTrainingRows(runs: IngestRun[]): TrainingLogRow[] {
  const rows: TrainingLogRow[] = runs.flatMap<TrainingLogRow>((run) => {
    if (!run.items.length) {
      return [
        {
          runId: run.id,
          itemId: null,
          status: run.status,
          timestamp: run.created_at,
          kindLabel: run.input_channel,
          title: run.id,
          preview: `Batch méret: ${run.batch_size}`,
        },
      ];
    }

    return run.items.map<TrainingLogRow>((item) => ({
      runId: run.id,
      itemId: item.id,
      status: item.status || run.status,
      timestamp: item.created_at || run.created_at,
      kindLabel: getItemKindLabel(item),
      title: getItemTitle(item),
      preview: getItemPreview(item),
    }));
  });

  return rows.sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
}
