import { Fragment, memo, useState } from "react";
import { sanitizeMessage } from "../../../utils/sanitize";
import api from "../../../api/axiosClient";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";

export type ChatMessageProps = {
  role: string;
  text: string;
  question?: string;
  queryRunId?: string | null;
  answerMode?: string;
  answerSource?: string;
  confidence?: number;
  evidence?: Array<Record<string, unknown>>;
  citedClaimIds?: string[];
  citedSentenceIds?: string[];
  citedSourceIds?: string[];
  queryProfile?: Record<string, unknown>;
  matchedChunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  contextBlocks?: Array<Record<string, unknown>>;
  promptContext?: Record<string, unknown>;
  encodedPromptContext?: string;
  debug?: Record<string, unknown> | null;
  restoredPiiSpans?: Array<{
    start: number;
    end: number;
    token?: string;
    value?: string;
    entity_type?: string;
  }>;
  actionLabel?: string;
  actionHref?: string;
  progressPercent?: number | null;
  sources?: Array<{
    kb_uuid: string;
    kb_name?: string;
    point_id: string;
    source_id?: string;
    title?: string;
    snippet?: string;
    source_url?: string;
    source_type?: string;
    file_ref?: string | null;
    display_type?: string;
    created_by?: number | null;
    created_by_label?: string;
    created_at?: string | null;
  }>;
};

function shortLabel(value: string, maxLength = 42): string {
  const text = value.trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function sourceDisplayName(source: NonNullable<ChatMessageProps["sources"]>[number], fallback: string): string {
  return source.file_ref || source.title || source.source_id || source.point_id || fallback;
}

function sourceDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const tag = locale === "en" ? "en-GB" : locale === "es" ? "es-ES" : "hu-HU";
  return parsed.toLocaleString(tag, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceTeacher(source: NonNullable<ChatMessageProps["sources"]>[number]): string {
  return source.created_by_label?.trim() || (source.created_by != null ? `#${source.created_by}` : "");
}

function sourceDisplayLabel(
  source: NonNullable<ChatMessageProps["sources"]>[number],
  fallback: string,
  locale: string
): string {
  const sourceType = String(source.source_type || source.display_type || "").trim().toLowerCase();
  const isFile = sourceType === "file" || Boolean(source.file_ref?.trim());
  const dateLabel = sourceDateTime(source.created_at, locale) || "ismeretlen dátum";
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

function filenameFromContentDisposition(value: string | undefined): string | null {
  if (!value) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encoded?.[1]) return decodeURIComponent(encoded[1]);
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain?.[1] ?? null;
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderTextWithRestoredHighlights(
  text: string,
  spans: Array<{ start: number; end: number; token?: string; entity_type?: string }>
) {
  const safeText = String(text || "");
  const validSpans = [...spans]
    .filter((span) => Number.isFinite(span.start) && Number.isFinite(span.end) && span.end > span.start)
    .sort((left, right) => left.start - right.start);
  if (!validSpans.length) return sanitizeMessage(safeText);
  const parts: any[] = [];
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

function ChatMessageInner({
  role,
  text,
  question,
  answerMode,
  evidence = [],
  citedSourceIds = [],
  actionLabel,
  actionHref,
  progressPercent,
  queryRunId,
  sources = [],
  promptContext,
  encodedPromptContext,
  restoredPiiSpans = [],
}: ChatMessageProps) {
  const { t, locale } = useTranslation();
  const isUser = role === "user";
  const isTrainingStatus = role === "training-status";
  const [sourceLoadingId, setSourceLoadingId] = useState<string | null>(null);
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [sourceTab, setSourceTab] = useState<"raw" | "parts" | "provenance">("raw");
  const [feedbackValue, setFeedbackValue] = useState<boolean | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const primarySource = sources[0];
  const sendFeedback = async (helpful: boolean) => {
    if (!queryRunId || feedbackLoading) return;
    setFeedbackLoading(true);
    try {
      await api.post("/chat/feedback", { trace_id: queryRunId, helpful });
      setFeedbackValue(helpful);
      toast.success(t("chat.feedbackSaved"));
    } catch {
      toast.error(t("chat.feedbackError"));
    } finally {
      setFeedbackLoading(false);
    }
  };
  const downloadSource = async (sourceId: string | undefined) => {
    if (!sourceId) {
      toast.error(t("chat.sourceMissingDownload"));
      return;
    }
    setSourceLoadingId(sourceId);
    try {
      const url = queryRunId
        ? `/chat/sources/${encodeURIComponent(queryRunId)}/${encodeURIComponent(sourceId)}/download`
        : `/knowledge/sources/${encodeURIComponent(sourceId)}/download`;
      const res = await api.get(url, {
        responseType: "blob",
      });
      const filename =
        filenameFromContentDisposition(res.headers["content-disposition"]) ||
        sourceDisplayName(
          sources.find((item) => (item.source_id || item.point_id) === sourceId) || primarySource || { point_id: sourceId, kb_uuid: "" },
          t("chat.sourceFallback")
        );
      downloadBlob(filename, res.data);
    } catch {
      toast.error(t("chat.sourceDownloadError"));
    } finally {
      setSourceLoadingId(null);
    }
  };
  const infoPrompt = String(promptContext?.informational_prompt || "").trim();
  const qaContext = String(promptContext?.qa_context || "").trim();
  const latestQuestion = String(promptContext?.latest_question || question || "").trim();
  const retrievalContext = String(promptContext?.retrieval_context || "").trim();
  const fallbackLlmContextFromSources = sources
    .map((source) => String(source.snippet || source.title || "").trim())
    .filter(Boolean)
    .join("\n\n---\n\n")
    .trim();
  const llmContextText = String(promptContext?.llm_context_text || fallbackLlmContextFromSources || "").trim();
  const encodedLlmContextText = String(promptContext?.encoded_llm_context_text || encodedPromptContext || "").trim();
  const piiApplied = typeof promptContext?.pii_applied === "boolean" ? promptContext.pii_applied : null;
  const piiReason = String(promptContext?.pii_reason || "").trim();
  const rawContextSentToLlm = String(promptContext?.raw_context_sent_to_llm || "").trim();
  const rawInputsBeforePii =
    promptContext?.raw_inputs_before_pii && typeof promptContext.raw_inputs_before_pii === "object"
      ? (promptContext.raw_inputs_before_pii as Record<string, unknown>)
      : null;
  const contextComponents =
    promptContext?.context_components && typeof promptContext.context_components === "object"
      ? (promptContext.context_components as Record<string, unknown>)
      : null;
  const answerInformationSources = Array.isArray(promptContext?.answer_information_sources)
    ? (promptContext.answer_information_sources as Array<Record<string, unknown>>)
    : [];
  const latestHits = Array.isArray(promptContext?.latest_hits) ? promptContext.latest_hits : [];
  const indexDebug = promptContext?.index_debug && typeof promptContext.index_debug === "object"
    ? promptContext.index_debug
    : null;
  const hasPromptContext =
    Boolean(infoPrompt || qaContext || latestQuestion || retrievalContext || llmContextText || encodedLlmContextText) ||
    latestHits.length > 0 ||
    Boolean(indexDebug);
  return (
    <div className="inline-flex max-w-[min(42rem,85%)] flex-col items-start">
      <div
        className={`whitespace-pre-wrap break-words px-4 py-2 text-sm leading-relaxed ${
          isTrainingStatus
            ? "rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)]"
            : isUser
            ? "rounded-3xl bg-[var(--color-primary)] text-[var(--color-on-primary)]"
            : "my-2 rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)]"
        }`}
      >
        {!isUser && !isTrainingStatus
          ? renderTextWithRestoredHighlights(text, restoredPiiSpans)
          : sanitizeMessage(text)}
        {typeof progressPercent === "number" ? (
          <div className="mt-2 h-1 w-[30px] overflow-hidden rounded-full bg-[var(--color-border)]">
            <div
              className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
              style={{ width: `${Math.max(0, Math.min(100, Math.round(progressPercent)))}%` }}
            />
          </div>
        ) : null}
      </div>
      {isTrainingStatus && actionLabel && actionHref ? (
        <a
          href={actionHref}
          className="mr-4 mt-1 rounded-full border border-[var(--color-border)] px-3 py-1 text-xs font-medium text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
        >
          {sanitizeMessage(actionLabel)}
        </a>
      ) : null}
      {!isUser && !isTrainingStatus && (sources.length > 0 || queryRunId || hasPromptContext) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 px-2 text-xs text-[var(--color-muted)]">
          {queryRunId ? (
            <div className="inline-flex items-center gap-1">
              <button
                type="button"
                onClick={() => sendFeedback(true)}
                disabled={feedbackLoading}
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full border transition hover:text-[var(--color-foreground)] disabled:opacity-60 ${
                  feedbackValue === true
                    ? "border-[var(--color-success-border)] text-[var(--color-success-text)]"
                    : "border-[var(--color-border)] text-[var(--color-muted)]"
                }`}
                aria-label={t("chat.feedbackLike")}
                title={t("chat.feedbackLike")}
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M7 10v10M7 10l4.5-6.5c.8-1.1 2.5-.6 2.5.8V9h4.2c1.2 0 2.1 1.1 1.9 2.2l-1.2 6.5A2.8 2.8 0 0 1 16.1 20H7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => sendFeedback(false)}
                disabled={feedbackLoading}
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full border transition hover:text-[var(--color-foreground)] disabled:opacity-60 ${
                  feedbackValue === false
                    ? "border-[var(--color-danger-border)] text-[var(--color-danger-text)]"
                    : "border-[var(--color-border)] text-[var(--color-muted)]"
                }`}
                aria-label={t("chat.feedbackUnlike")}
                title={t("chat.feedbackUnlike")}
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M17 14V4M17 14l-4.5 6.5c-.8 1.1-2.5.6-2.5-.8V15H5.8c-1.2 0-2.1-1.1-1.9-2.2l1.2-6.5A2.8 2.8 0 0 1 7.9 4H17"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => setSourceModalOpen(true)}
            className="rounded-full border border-[var(--color-border)] bg-transparent px-2.5 py-1 font-semibold text-[var(--color-muted)] transition hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
          >
            {t("chat.sourceFallback")}
          </button>
        </div>
      )}
      {sourceModalOpen ? (
        <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/55 p-4">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-[var(--color-foreground)] shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">{t("chat.sourceFallback")} - AI prompt context</h3>
              <button
                type="button"
                onClick={() => setSourceModalOpen(false)}
                className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs text-[var(--color-muted)] hover:bg-[var(--color-border)]/20"
              >
                Bezár
              </button>
            </div>
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              <button
                type="button"
                onClick={() => setSourceTab("raw")}
                className={`rounded-full border px-2.5 py-1 ${sourceTab === "raw" ? "border-[var(--color-primary)] text-[var(--color-primary)]" : "border-[var(--color-border)] text-[var(--color-muted)]"}`}
              >
                Teljes nyers context
              </button>
              <button
                type="button"
                onClick={() => setSourceTab("parts")}
                className={`rounded-full border px-2.5 py-1 ${sourceTab === "parts" ? "border-[var(--color-primary)] text-[var(--color-primary)]" : "border-[var(--color-border)] text-[var(--color-muted)]"}`}
              >
                Context összetevők
              </button>
              <button
                type="button"
                onClick={() => setSourceTab("provenance")}
                className={`rounded-full border px-2.5 py-1 ${sourceTab === "provenance" ? "border-[var(--color-primary)] text-[var(--color-primary)]" : "border-[var(--color-border)] text-[var(--color-muted)]"}`}
              >
                Válaszinformáció forrása
              </button>
            </div>
            <div className="space-y-3 text-[12px] leading-relaxed">
              {sourceTab === "raw" ? (
                <div>
                  <div className="mb-1 font-semibold">Az API híváskor AI-nak küldött teljes nyers tartalom</div>
                  <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                    {sanitizeMessage(
                      rawContextSentToLlm ||
                      (Array.isArray(promptContext?.messages_sent_to_llm)
                        ? JSON.stringify(promptContext.messages_sent_to_llm, null, 2)
                        : "-")
                    )}
                  </div>
                  <div className="mb-1 mt-3 font-semibold">PII előtti nyers bemenet (validáláshoz)</div>
                  <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                    {sanitizeMessage(
                      rawInputsBeforePii
                        ? JSON.stringify(rawInputsBeforePii, null, 2)
                        : "-"
                    )}
                  </div>
                </div>
              ) : null}

              {sourceTab === "parts" ? (
                <>
                  <div>
                    <div className="mb-1 font-semibold">Alap context</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                      {sanitizeMessage(String(contextComponents?.alap_context || llmContextText || "-"))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">Előzmények (csak értelmezéshez, nem bizonyíték)</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                      {sanitizeMessage(String(contextComponents?.elozmenyek || qaContext || "-"))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">Kérdés</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                      {sanitizeMessage(String(contextComponents?.kerdes || latestQuestion || "-"))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">Válaszinformáció</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                      {sanitizeMessage(
                        JSON.stringify(
                          contextComponents?.valaszinformacio || {
                            answer_mode: answerMode || "",
                            evidence,
                            cited_source_ids: citedSourceIds,
                          },
                          null,
                          2
                        )
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">AI-nak küldött deperszonalizált context</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">{sanitizeMessage(encodedLlmContextText || llmContextText || "-")}</div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">PII deperszonalizáció állapota</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                      {sanitizeMessage(
                        `${piiApplied === true ? "lefutott" : piiApplied === false ? "nem futott" : "ismeretlen"}${piiReason ? ` - ${piiReason}` : ""}`
                      )}
                    </div>
                  </div>
                </>
              ) : null}

              {sourceTab === "provenance" ? (
                <>
                  <div>
                    <div className="mb-1 font-semibold">Válaszinformáció kontextus-eredete</div>
                    <div className="space-y-2">
                      {answerInformationSources.length > 0 ? answerInformationSources.map((row, idx) => (
                        <div key={`answer-src-${idx}`} className="rounded-lg border border-[var(--color-border)] p-2">
                          <div className="text-[11px] text-[var(--color-muted)]">
                            forrás: {sanitizeMessage(String(row.source_id || "-"))} | claim: {sanitizeMessage(String(row.claim_id || "-"))} | sentence: {sanitizeMessage(String(row.sentence_id || "-"))}
                          </div>
                          <div className="mt-1 whitespace-pre-wrap">{sanitizeMessage(String(row.claim_text || row.sentence_text || ""))}</div>
                        </div>
                      )) : (
                        <div className="rounded-lg border border-[var(--color-border)] p-2 text-[var(--color-muted)]">Nincs dedikált answer-source mapping.</div>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">Források</div>
                    <div className="space-y-1">
                      {sources.map((s, idx) => (
                        <div key={`${s.kb_uuid}-${s.point_id}-${idx}`} className="leading-snug">
                          <span className="text-[var(--color-muted)]">
                            {sanitizeMessage(sourceDisplayLabel(s, t("chat.sourceFallback"), locale))}
                          </span>
                          <span className="ml-2 text-[var(--color-muted)]">•</span>
                          <button
                            type="button"
                            onClick={() => downloadSource(s.source_id)}
                            disabled={!s.source_id || sourceLoadingId === s.source_id}
                            className="ml-1 underline text-left text-[var(--color-primary)] hover:text-[var(--color-foreground)] disabled:opacity-60"
                          >
                            Tartalom
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold">Miért ezt találta? (index nézet)</div>
                    <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2 text-[11px]">
                      {sanitizeMessage(indexDebug ? JSON.stringify(indexDebug, null, 2) : "Nincs index debug adat.")}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default memo(ChatMessageInner);
