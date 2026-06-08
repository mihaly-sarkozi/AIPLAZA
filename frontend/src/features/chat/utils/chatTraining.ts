import { formatInteger, numberValue } from "./chatNumbers";

export function exactTrainingCharCount(
  run:
    | {
        metadata?: Record<string, unknown>;
        items?: Array<{ metadata?: Record<string, unknown>; char_count?: unknown }>;
      }
    | null
    | undefined
): number {
  const total = numberValue(run?.metadata?.total_char_count);
  if (total > 0) return total;
  return (run?.items ?? []).reduce((sum, item) => {
    const fromMetadata = numberValue(item.metadata?.char_count);
    if (fromMetadata > 0) return sum + fromMetadata;
    return sum + numberValue(item.char_count);
  }, 0);
}

export function resolveTrainingCharCount(
  run: Parameters<typeof exactTrainingCharCount>[0],
  fallbackCount?: number
): number {
  const fromRun = exactTrainingCharCount(run);
  if (fromRun > 0) return fromRun;
  return Math.max(0, numberValue(fallbackCount));
}

export function isDuplicateOnlyTrainingRun(
  run:
    | {
        completed_count?: number;
        duplicate_count?: number;
        items?: Array<{ status?: string }>;
      }
    | null
    | undefined
): boolean {
  if (!run) return false;
  const items = run.items ?? [];
  if (items.length > 0) {
    return items.every((item) => item.status === "duplicate");
  }
  return numberValue(run.duplicate_count) > 0 && numberValue(run.completed_count) === 0;
}

export function estimateFileCharactersForProgress(file: File): number {
  const name = file.name.toLowerCase();
  const multiplier = 1.3;
  if (name.endsWith(".txt")) return Math.max(1, Math.round(file.size * multiplier));
  if (name.endsWith(".pdf")) return Math.max(1, Math.round(file.size * 0.06 * multiplier));
  if (name.endsWith(".docx")) return Math.max(1, Math.round(file.size * 0.25 * multiplier));
  return Math.max(1, Math.round(file.size * 0.35 * multiplier));
}

export function estimateCountingDurationMs(file: File): number {
  const mb = file.size / (1024 * 1024);
  return Math.max(1500, Math.min(15000, Math.round(1200 + mb * 1800)));
}

export function estimateTrainingDurationMs(characterCount: number): number {
  const chars = Math.max(0, characterCount);
  return Math.max(20_000, Math.min(900_000, Math.round(20_000 + chars / 1.2)));
}

export function estimatedTrainingProgress(elapsedMs: number, durationMs: number): number {
  const baseRatio = Math.max(0, elapsedMs / Math.max(1, durationMs));
  const ratio = Math.min(2, baseRatio);
  if (ratio <= 1) {
    const eased = 1 - Math.pow(1 - ratio, 2);
    return Math.round(6 + eased * 88);
  }
  const overtimeRatio = Math.min(1, ratio - 1);
  return Math.round(94 + overtimeRatio * 5);
}

export function buildTrainingSuccessDetail(
  charCount: number,
  locale: string,
  t: (key: string) => string
): string {
  const base = t("chat.trainingCompletedPercent");
  if (charCount <= 0) return base;
  return `${base} ${t("chat.fileCharacterCount").replace("{{count}}", formatInteger(charCount, locale))}`;
}

export function combineTrainingProgress(actualProgress: number, visualProgress: number): number {
  const actual = Math.max(0, Math.min(100, Math.round(actualProgress)));
  const visual = Math.max(0, Math.min(99, Math.round(visualProgress)));
  if (actual <= 0) return visual;
  if (actual >= 100) return 100;
  return Math.max(actual, visual);
}
