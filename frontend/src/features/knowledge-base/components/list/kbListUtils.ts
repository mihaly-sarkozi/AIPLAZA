import type { KbItem } from "../../hooks/useKb";

export const PERM_NONE = "none";
export const PERM_USE = "use";
export const PERM_TRAIN = "train";
export const KB_NAME_MAX_LENGTH = 200;

export type KbFormData = {
  name: string;
  description: string;
};

export type KbPermissionRow = {
  id: number;
  email: string;
  name?: string | null;
  permission: string;
  role?: string;
};

export function formatBytes(value: number | null | undefined): string {
  const bytes = Math.max(0, Number(value || 0));
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: size >= 10 ? 1 : 2 }).format(size)} ${units[unitIndex]}`;
}

export function formatInteger(value: number | null | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Math.max(0, Number(value || 0)));
}

export function formatThousands(value: number | null | undefined): string {
  const safeValue = Math.max(0, Number(value || 0));
  if (safeValue < 1000) return formatInteger(safeValue);
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: 1 }).format(safeValue / 1000)}E`;
}

export function metricValue(
  kb: KbItem,
  key: "file_bytes" | "database_bytes" | "qdrant_bytes" | "total_bytes" | "training_char_count"
): number {
  const value = kb.storage_metrics?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function isDeletedKb(kb: KbItem): boolean {
  return kb.status === "deleted" || Boolean(kb.deleted_at);
}

export function nameMaxLengthMessage(t: (key: string) => string): string {
  return t("kb.nameMaxLength").replace("{{count}}", String(KB_NAME_MAX_LENGTH));
}
