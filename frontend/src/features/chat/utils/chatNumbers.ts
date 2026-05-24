export function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function usagePercent(used: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((used / total) * 100)));
}

export function localeTag(locale: string): string {
  if (locale === "en") return "en-GB";
  if (locale === "es") return "es-ES";
  return "hu-HU";
}

export function formatCompactNumber(value: number, locale: string): string {
  return value.toLocaleString(localeTag(locale), {
    notation: value >= 10_000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  });
}

export function formatInteger(value: number, locale: string): string {
  return Math.max(0, Number(value || 0)).toLocaleString(localeTag(locale));
}
