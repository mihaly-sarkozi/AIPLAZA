import { Fragment, type ReactNode } from "react";
import { sanitizeMessage } from "../../../utils/sanitize";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { formatDateTime } from "../../../utils/dateTimeFormatting";
import type { ChatSource, RestoredPiiSpan } from "../components/message/chatMessageTypes";

export function shortLabel(value: string, maxLength = 42): string {
  const text = value.trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

export function sourceDisplayName(source: ChatSource, fallback: string): string {
  return source.file_ref || source.title || source.source_id || source.point_id || fallback;
}

function sourceDateTime(
  value: string | null | undefined,
  locale: string,
  timezone?: SettingsTimezone | string,
  dateFormat?: SettingsDateFormat,
  timeFormat?: SettingsTimeFormat
): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return formatDateTime(value, { locale, timezone, dateFormat, timeFormat });
}

function sourceTeacher(source: ChatSource): string {
  return source.created_by_label?.trim() || (source.created_by != null ? `#${source.created_by}` : "");
}

export function sourceDisplayLabel(
  source: ChatSource,
  fallback: string,
  locale: string,
  timezone?: SettingsTimezone | string,
  dateFormat?: SettingsDateFormat,
  timeFormat?: SettingsTimeFormat
): string {
  const sourceType = String(source.source_type || source.display_type || "").trim().toLowerCase();
  const isFile = sourceType === "file" || Boolean(source.file_ref?.trim());
  const dateLabel = sourceDateTime(source.created_at, locale, timezone, dateFormat, timeFormat) || "ismeretlen dátum";
  const teacherLabel = sourceTeacher(source) || "ismeretlen tanító";
  const kbLabel = String(source.kb_name || source.kb_uuid || "").trim() || "ismeretlen tudástár";
  const trainingLabel = isFile ? "fájlos tanítás" : "Chatből tanított szöveg";
  const title = shortLabel(sourceDisplayName(source, fallback), isFile ? 48 : 70);
  const normalizedTitle = title.trim().toLowerCase();
  const normalizedTrainingLabel = trainingLabel.trim().toLowerCase();
  if (normalizedTitle === normalizedTrainingLabel) {
    return `${dateLabel} • ${kbLabel} • ${teacherLabel} • ${trainingLabel}`;
  }
  return `${dateLabel} • ${kbLabel} • ${teacherLabel} • ${trainingLabel} • ${title}`;
}

export function filenameFromContentDisposition(value: string | undefined): string | null {
  if (!value) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encoded?.[1]) return decodeURIComponent(encoded[1]);
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain?.[1] ?? null;
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function renderTextWithRestoredHighlights(text: string, spans: RestoredPiiSpan[]): ReactNode {
  const safeText = String(text || "");
  const validSpans = [...spans]
    .filter((span) => Number.isFinite(span.start) && Number.isFinite(span.end) && span.end > span.start)
    .sort((left, right) => left.start - right.start);
  if (!validSpans.length) return sanitizeMessage(safeText);
  const parts: ReactNode[] = [];
  let cursor = 0;
  validSpans.forEach((span, index) => {
    const start = Math.max(0, Math.min(safeText.length, Math.round(span.start)));
    const end = Math.max(start, Math.min(safeText.length, Math.round(span.end)));
    if (start < cursor) return;
    if (start > cursor) {
      parts.push(<Fragment key={`plain-${index}`}>{sanitizeMessage(safeText.slice(cursor, start))}</Fragment>);
    }
    parts.push(
      <mark
        key={`pii-${index}`}
        className="rounded bg-amber-200/60 px-0.5 text-[var(--color-foreground)]"
        title={`Rehidratált PII: ${span.entity_type || "pii"} (${span.token || ""})`}
      >
        {sanitizeMessage(safeText.slice(start, end))}
      </mark>
    );
    cursor = end;
  });
  if (cursor < safeText.length) {
    parts.push(<Fragment key="plain-tail">{sanitizeMessage(safeText.slice(cursor))}</Fragment>);
  }
  return parts;
}
