import type { IngestRun } from "../services";

const ACTIVE_TRAINING_STATUSES = new Set([
  "received",
  "queued",
  "processing",
  "pending",
  "running",
  "accepted",
]);
type Translate = (key: string) => string;

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

export function isTrainingActive(status: string | undefined): boolean {
  return ACTIVE_TRAINING_STATUSES.has((status ?? "").trim());
}

const TERMINAL_TRAINING_STATUSES = new Set(["completed", "partial_success", "failed", "cancelled"]);

export function isTerminalTrainingStatus(status: string | undefined): boolean {
  return TERMINAL_TRAINING_STATUSES.has((status ?? "").trim());
}

/** Aktív futásnál pollolunk; lezárt vagy ismeretlen állapotnál nem. */
export function getTrainingRunRefetchInterval(status: string | undefined): number | false {
  return isTrainingActive(status) ? 1500 : false;
}

export function getRunProgressSummary(run: IngestRun | undefined): RunProgressSummary {
  const raw = run?.metadata?.progress_summary;
  if (!raw || typeof raw !== "object") return {};
  return raw as RunProgressSummary;
}

export function getTrainingProgress(run: IngestRun | undefined): number {
  if (!run) return 0;
  if (run.status === "completed" || run.status === "partial_success") return 100;
  const summary = getRunProgressSummary(run);
  if (typeof summary.overall_percent === "number") {
    const cap = isTrainingActive(run.status) ? 99 : 100;
    return Math.max(0, Math.min(cap, Math.round(summary.overall_percent)));
  }
  const total = Math.max(run.batch_size || 0, 1);
  const done = run.completed_count + run.failed_count + run.duplicate_count + run.rejected_count;
  const cap = isTrainingActive(run.status) ? 99 : 100;
  return Math.max(0, Math.min(cap, Math.round((done / total) * 100)));
}

export function getTrainingStatusLabel(run: IngestRun | undefined, t?: Translate): string {
  const status = run?.status ?? "";
  if (!status) return "";
  if (status === "received" || status === "pending") return t ? t("chat.trainingStatusReceived") : status;
  if (status === "queued") return t ? t("chat.trainingStatusQueued") : "queued";
  if (status === "processing" || status === "running") return t ? t("chat.trainingStatusProcessing") : status;
  if (status === "accepted") return t ? t("chat.trainingStatusProcessing") : "accepted";
  if (status === "completed") return t ? t("chat.trainingStatusCompleted") : "completed";
  if (status === "failed") return t ? t("chat.trainingStatusFailed") : "failed";
  if (status === "partial_success") return t ? t("chat.trainingStatusPartialSuccess") : "partial_success";
  return status;
}

export function getTrainingStatusDetail(run: IngestRun | undefined, t?: Translate): string {
  if (!run) return "";
  const summary = getRunProgressSummary(run);
  if (typeof summary.active_message === "string" && summary.active_message.trim()) {
    return summary.active_message;
  }
  if (typeof summary.active_module_label === "string" && summary.active_module_label.trim()) {
    return summary.active_module_label;
  }
  return getTrainingStatusLabel(run, t);
}

export function getTrainingFailureMessage(run: IngestRun | undefined, t?: Translate): string | null {
  if (!run) return null;
  const summary = getRunProgressSummary(run);
  if (typeof summary.last_error_message === "string" && summary.last_error_message.trim()) {
    if (typeof summary.stopped_at === "string" && summary.stopped_at.trim()) {
      return `${summary.last_error_message} (${t ? t("chat.stoppedAt") : "stopped at"}: ${summary.stopped_at})`;
    }
    return summary.last_error_message;
  }
  const failedItem = run.items.find((item) => item.error_message?.trim());
  if (failedItem?.error_message) return failedItem.error_message;
  const metadataError = run.metadata?.error_message;
  return typeof metadataError === "string" && metadataError.trim() ? metadataError : null;
}
