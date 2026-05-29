import type { IngestItem, IngestRun } from "../services";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { formatDateTime } from "../../../utils/dateTimeFormatting";

export const ACTIVE_RUN_STATUSES = new Set(["received", "queued", "processing"]);

export type TrainingLogRow = {
  runId: string;
  itemId: string | null;
  sourceId: string | null;
  status: string;
  timestamp: string;
  kindLabel: string;
  title: string;
  preview: string;
  createdByLabel: string;
  charCount: number;
  sentenceCount: number;
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

export type ProcessingPreviewLabels = {
  noData: string;
  processed: string;
  sentence: string;
  character: string;
};

export type TrainingKindLabels = {
  file: string;
  text: string;
  url: string;
  unknown: string;
};

const DEFAULT_PROCESSING_PREVIEW_LABELS: ProcessingPreviewLabels = {
  noData: "nincs adat",
  processed: "Feldolgozva",
  sentence: "mondat",
  character: "karakter",
};

const DEFAULT_TRAINING_KIND_LABELS: TrainingKindLabels = {
  file: "Fájl",
  text: "Szöveg",
  url: "Hivatkozás",
  unknown: "Ismeretlen",
};

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

export function formatTimestamp(
  value: string | null | undefined,
  options?: {
    locale?: string;
    timezone?: SettingsTimezone | string;
    dateFormat?: SettingsDateFormat;
    timeFormat?: SettingsTimeFormat;
  }
): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatDateTime(value, {
    locale: options?.locale ?? "hu",
    timezone: options?.timezone,
    dateFormat: options?.dateFormat,
    timeFormat: options?.timeFormat,
  });
}

export function formatInteger(value: number | null | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Math.max(0, Math.round(value ?? 0)));
}

export function getNumericMetadataValue(metadata: Record<string, unknown> | null | undefined, key: string): number {
  const value = metadata?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
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
    case "partial_success":
      return "Részben kész";
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
    case "partial_success":
      return "bg-teal-500/10 text-teal-700 dark:text-teal-300";
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

function getInputKindLabel(inputType: string | null | undefined, labels: TrainingKindLabels): string {
  switch ((inputType || "").trim()) {
    case "file":
      return labels.file;
    case "text":
      return labels.text;
    case "url":
      return labels.url;
    default:
      return inputType || labels.unknown;
  }
}

export function getItemKindLabel(
  item: Pick<IngestItem, "input_type"> | null | undefined,
  labels: TrainingKindLabels = DEFAULT_TRAINING_KIND_LABELS
): string {
  return getInputKindLabel(item?.input_type, labels);
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
    return "";
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
  if (run.status === "completed" || run.status === "partial_success") return 100;
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

export function getItemProcessingPreview(
  item: IngestItem | null | undefined,
  labels: ProcessingPreviewLabels = DEFAULT_PROCESSING_PREVIEW_LABELS
): string {
  if (!item) return labels.noData;
  const percent = getItemProgressPercent(item);
  const sentenceCount = getNumericMetadataValue(item.metadata, "sentence_count");
  const charCount = getNumericMetadataValue(item.metadata, "char_count");
  const summary = getItemProcessingSummary(item);
  const parts = [`${labels.processed} ${percent}%`];
  if (sentenceCount > 0) parts.push(`${formatInteger(sentenceCount)} ${labels.sentence}`);
  if (charCount > 0) parts.push(`${formatInteger(charCount)} ${labels.character}`);
  const label = summary.document_progress?.label || item.progress_message;
  if (label && percent < 100) parts.push(String(label));
  return parts.join(" | ");
}

export function getRunProcessingPreview(
  run: IngestRun | null | undefined,
  labels: ProcessingPreviewLabels = DEFAULT_PROCESSING_PREVIEW_LABELS
): string {
  if (!run) return labels.noData;
  const percent = getRunProgressPercent(run);
  const sentenceCount = getNumericMetadataValue(run.metadata, "total_sentence_count");
  const charCount = getNumericMetadataValue(run.metadata, "total_char_count");
  const parts = [`${labels.processed} ${percent}%`];
  if (sentenceCount > 0) parts.push(`${formatInteger(sentenceCount)} ${labels.sentence}`);
  if (charCount > 0) parts.push(`${formatInteger(charCount)} ${labels.character}`);
  return parts.join(" | ");
}

export function getItemProgressPercent(item: IngestItem | null | undefined): number {
  if (!item) return 0;
  if (["completed", "duplicate", "rejected", "failed"].includes(item.status)) return 100;
  const progress = getItemProcessingSummary(item).document_progress;
  if (typeof progress?.progress_percent === "number") {
    const percent = Math.max(0, Math.min(100, Math.round(progress.progress_percent)));
    if (progress.phase === "file_character_count") {
      return Math.max(5, Math.min(20, Math.round(percent * 0.2)));
    }
    if (progress.phase === "parser") {
      return Math.max(20, Math.min(50, Math.round(percent * 0.5)));
    }
    if (progress.phase === "sentence_interpretation") {
      return Math.max(55, Math.min(99, 55 + Math.round(percent * 0.44)));
    }
    return percent;
  }
  return 0;
}

export function getRunPrimaryItem(run: IngestRun, preferredItemId?: string | null): IngestItem | null {
  if (preferredItemId) {
    const selected = run.items.find((item) => item.id === preferredItemId);
    if (selected) return selected;
  }
  return run.items[0] ?? null;
}

export function buildTrainingRows(
  runs: IngestRun[],
  kindLabels: TrainingKindLabels = DEFAULT_TRAINING_KIND_LABELS
): TrainingLogRow[] {
  const rows: TrainingLogRow[] = runs.flatMap<TrainingLogRow>((run) => {
    if (!run.items.length) {
      return [
        {
          runId: run.id,
          itemId: null,
          sourceId: null,
          status: run.status,
          timestamp: run.created_at,
          kindLabel: getInputKindLabel(run.input_channel, kindLabels),
          title: run.id,
          preview: `Batch méret: ${run.batch_size}`,
          createdByLabel: run.created_by_label || "Ismeretlen",
          charCount: getNumericMetadataValue(run.metadata, "total_char_count"),
          sentenceCount: getNumericMetadataValue(run.metadata, "total_sentence_count"),
        },
      ];
    }

    return run.items.map<TrainingLogRow>((item) => ({
      runId: run.id,
      itemId: item.id,
      sourceId: item.source_id || (typeof item.metadata?.source_id === "string" ? item.metadata.source_id : null),
      status: item.status || run.status,
      timestamp: item.created_at || run.created_at,
      kindLabel: getItemKindLabel(item, kindLabels),
      title: getItemTitle(item),
      preview: getItemPreview(item),
      createdByLabel: item.created_by_label || run.created_by_label || "Ismeretlen",
      charCount: getNumericMetadataValue(item.metadata, "char_count"),
      sentenceCount: getNumericMetadataValue(item.metadata, "sentence_count"),
    }));
  });

  return rows.sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
}
