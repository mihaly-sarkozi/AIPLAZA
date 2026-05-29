import type { ChatMessageType } from "../types";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { formatDateTime } from "../../../utils/dateTimeFormatting";

export function serializeProcessToTxt({
  locale,
  mode,
  selectedKbLabel,
  messages,
  contextNotice,
  timezone,
  dateFormat,
  timeFormat,
}: {
  locale: string;
  mode: "query" | "train";
  selectedKbLabel: string;
  messages: ChatMessageType[];
  contextNotice: string | null;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
}): string {
  const lines: string[] = [];
  const now = formatDateTime(new Date().toISOString(), { locale, timezone, dateFormat, timeFormat });
  lines.push("=== AIPLAZA Chat folyamat export ===");
  lines.push(`Export időpont: ${now}`);
  lines.push(`Mód: ${mode === "train" ? "Tanítás" : "Lekérdezés"}`);
  lines.push(`Kiválasztott tudástár: ${selectedKbLabel}`);
  lines.push("");
  if (contextNotice?.trim()) {
    lines.push("=== Kontextus figyelmeztetés ===");
    lines.push(contextNotice.trim());
    lines.push("");
  }
  lines.push("=== Üzenetfolyam ===");
  messages.forEach((msg, idx) => {
    lines.push(`-- #${idx + 1} (${msg.role}) --`);
    lines.push((msg.text || "").trim() || "(üres)");
    if (msg.aiContextContent && String(msg.aiContextContent).trim() && String(msg.aiContextContent).trim() !== String(msg.text || "").trim()) {
      lines.push(`ai_context_content: ${String(msg.aiContextContent).trim()}`);
    }
    if (msg.queryRunId) lines.push(`query_run_id: ${msg.queryRunId}`);
    if (msg.answerMode) lines.push(`answer_mode: ${msg.answerMode}`);
    if (msg.answerSource) lines.push(`answer_source: ${msg.answerSource}`);
    if (typeof msg.confidence === "number") lines.push(`confidence: ${msg.confidence}`);
    if (Array.isArray(msg.sources) && msg.sources.length > 0) {
      lines.push("források:");
      msg.sources.forEach((src, srcIdx) => {
        lines.push(
          `  ${srcIdx + 1}. kb=${src.kb_name || src.kb_uuid || "-"} | source_id=${src.source_id || "-"} | title=${src.title || "-"}`
        );
      });
    }
    if (msg.promptContext && typeof msg.promptContext === "object") {
      lines.push("prompt_context:");
      lines.push(JSON.stringify(msg.promptContext, null, 2));
    }
    if (msg.debug && typeof msg.debug === "object") {
      lines.push("debug:");
      lines.push(JSON.stringify(msg.debug, null, 2));
    }
    lines.push("");
  });
  return lines.join("\n").trim();
}

export function downloadTxt(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
