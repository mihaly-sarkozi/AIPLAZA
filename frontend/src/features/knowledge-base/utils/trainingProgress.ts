import type { IngestRun } from "../services";

const ACTIVE_TRAINING_STATUSES = new Set(["received", "queued", "processing"]);

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

export function getRunProgressSummary(run: IngestRun | undefined): RunProgressSummary {
  const raw = run?.metadata?.progress_summary;
  if (!raw || typeof raw !== "object") return {};
  return raw as RunProgressSummary;
}

export function getTrainingProgress(run: IngestRun | undefined): number {
  if (!run) return 0;
  if (run.status === "completed") return 100;
  const summary = getRunProgressSummary(run);
  if (typeof summary.overall_percent === "number") {
    return Math.max(0, Math.min(100, Math.round(summary.overall_percent)));
  }
  const total = Math.max(run.batch_size || 0, 1);
  const done = run.completed_count + run.failed_count + run.duplicate_count + run.rejected_count;
  return Math.max(0, Math.min(99, Math.round((done / total) * 100)));
}

export function getTrainingStatusLabel(run: IngestRun | undefined): string {
  const status = run?.status ?? "";
  if (!status) return "";
  if (status === "received") return "Fogadva";
  if (status === "queued") return "Sorban";
  if (status === "processing") return "Feldolgozás";
  if (status === "completed") return "Kész";
  if (status === "failed") return "Hiba";
  if (status === "partial_success") return "Részben kész";
  return status;
}

export function getTrainingStatusDetail(run: IngestRun | undefined): string {
  if (!run) return "";
  const summary = getRunProgressSummary(run);
  if (typeof summary.active_message === "string" && summary.active_message.trim()) {
    return summary.active_message;
  }
  if (typeof summary.active_module_label === "string" && summary.active_module_label.trim()) {
    return summary.active_module_label;
  }
  return getTrainingStatusLabel(run);
}

export function getTrainingFailureMessage(run: IngestRun | undefined): string | null {
  if (!run) return null;
  const summary = getRunProgressSummary(run);
  if (typeof summary.last_error_message === "string" && summary.last_error_message.trim()) {
    if (typeof summary.stopped_at === "string" && summary.stopped_at.trim()) {
      return `${summary.last_error_message} (megállt itt: ${summary.stopped_at})`;
    }
    return summary.last_error_message;
  }
  const failedItem = run.items.find((item) => item.error_message?.trim());
  if (failedItem?.error_message) return failedItem.error_message;
  const failedEvent = [...run.events].reverse().find((event) => event.status === "failed" && event.message?.trim());
  if (failedEvent?.message) return failedEvent.message;
  const metadataError = run.metadata?.error_message;
  return typeof metadataError === "string" && metadataError.trim() ? metadataError : null;
}
