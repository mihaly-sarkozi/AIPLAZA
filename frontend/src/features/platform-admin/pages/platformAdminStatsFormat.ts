export function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Number(value || 0));
}

export function formatBytes(value: number | null | undefined): string {
  const bytes = Number(value || 0);
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toLocaleString("hu-HU", { maximumFractionDigits: 1 })} ${units[index]}`;
}

export function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("hu-HU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatDateOnly(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("hu-HU", { dateStyle: "medium" }).format(date);
}

export function formatMoneyCents(value: number | null | undefined): string {
  return `${(Number(value || 0) / 100).toLocaleString("hu-HU", { maximumFractionDigits: 2 })} EUR`;
}

