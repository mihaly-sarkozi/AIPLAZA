import { memo, useState } from "react";
import { toast } from "sonner";

import api from "../../../api/axiosClient";
import { useTranslation } from "../../../i18n";
import { sanitizeMessage } from "../../../utils/sanitize";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import ChatFeedbackControls from "./message/ChatFeedbackControls";
import ChatMessageBubble from "./message/ChatMessageBubble";
import TextTrainingOutcomeIndicator from "./message/TextTrainingOutcomeIndicator";
import TextTrainingPendingIndicator from "./message/TextTrainingPendingIndicator";
import type { TextTrainingOutcome } from "../utils/textTrainingMessage";
import ChatSourceModal from "./message/ChatSourceModal";
import type { ChatSource, RestoredPiiSpan } from "./message/chatMessageTypes";
import { downloadBlob, filenameFromContentDisposition, sourceDisplayName } from "../utils/chatMessageFormatting";

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
  citations?: string[];
  promptContext?: Record<string, unknown>;
  encodedPromptContext?: string;
  debug?: Record<string, unknown> | null;
  restoredPiiSpans?: RestoredPiiSpan[];
  actionLabel?: string;
  actionHref?: string;
  progressPercent?: number | null;
  textTrainingPending?: boolean;
  textTrainingInProgress?: boolean;
  textTrainingProgressPercent?: number;
  textTrainingOutcome?: TextTrainingOutcome;
  textTrainingOutcomeDetail?: string;
  excludeFromAiContext?: boolean;
  sources?: ChatSource[];
};

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
  textTrainingPending,
  textTrainingInProgress,
  textTrainingProgressPercent,
  textTrainingOutcome,
  textTrainingOutcomeDetail,
  excludeFromAiContext,
  queryRunId,
  sources = [],
  matchedChunks = [],
  contextBlocks = [],
  citations = [],
  debug = null,
  promptContext,
  encodedPromptContext,
  restoredPiiSpans = [],
}: ChatMessageProps) {
  const { t, locale } = useTranslation();
  const { data: settings } = useLocaleSettings();
  const isUser = role === "user";
  const isTrainingUserBubble = isUser && Boolean(excludeFromAiContext);
  const isTrainingStatus = role === "training-status";
  const [sourceLoadingId, setSourceLoadingId] = useState<string | null>(null);
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [sourceTab, setSourceTab] = useState<"sources" | "context_blocks" | "index_hits" | "prompt" | "raw" | "parts" | "provenance" | "debug">("sources");
  const [feedbackValue, setFeedbackValue] = useState<boolean | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const primarySource = sources[0];
  const promptContextDetail = buildPromptContextDetail({ promptContext, encodedPromptContext, sources, question });
  const hasPromptContext =
    Boolean(
      promptContextDetail.infoPrompt ||
        promptContextDetail.qaContext ||
        promptContextDetail.latestQuestion ||
        promptContextDetail.retrievalContext ||
        promptContextDetail.llmContextText ||
        promptContextDetail.encodedLlmContextText
    ) ||
    promptContextDetail.latestHits.length > 0 ||
    Boolean(promptContextDetail.indexDebug);

  const normalizedAnswerMode = String(answerMode || "").toUpperCase();
  const canShowEvidenceUi =
    !isUser &&
    !isTrainingStatus &&
    normalizedAnswerMode !== "NO_ANSWER" &&
    normalizedAnswerMode !== "BLOCKED_NOT_READY" &&
    (sources.length > 0 || (hasPromptContext && normalizedAnswerMode === "ANSWERED"));

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
      const matchedSource = sources.find((item) => (item.source_id || item.point_id) === sourceId);
      const url =
        matchedSource?.download_url ||
        (queryRunId
          ? `/chat/sources/${encodeURIComponent(queryRunId)}/${encodeURIComponent(sourceId)}/download`
          : `/knowledge/sources/${encodeURIComponent(sourceId)}/download`);
      const res = await api.get(url, { responseType: "blob" });
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

  const showTextTrainingOutcome = isUser && textTrainingOutcome && textTrainingOutcomeDetail;
  const showTextTrainingPending =
    isUser && Boolean(textTrainingPending) && !textTrainingOutcome && Boolean(textTrainingInProgress);
  const pendingDetail =
    typeof textTrainingProgressPercent === "number" && textTrainingProgressPercent > 0
      ? t("chat.trainingProgressPercent").replace("{{percent}}", String(Math.round(textTrainingProgressPercent)))
      : t("chat.trainingInProgress");

  return (
    <div className={`inline-flex max-w-[min(42rem,85%)] flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div className={`flex items-center gap-1.5 ${isUser ? "mr-4" : ""}`}>
        <ChatMessageBubble
          isUser={isUser}
          isTrainingUserBubble={isTrainingUserBubble}
          isTrainingStatus={isTrainingStatus}
          text={text}
          progressPercent={progressPercent}
          restoredPiiSpans={restoredPiiSpans}
          trainingContentLabel={isTrainingUserBubble ? t("chat.trainingContentPrefix") : undefined}
        />
        {showTextTrainingPending ? (
          <TextTrainingPendingIndicator detail={pendingDetail} ariaLabel={pendingDetail} />
        ) : null}
        {showTextTrainingOutcome ? (
          <TextTrainingOutcomeIndicator
            outcome={textTrainingOutcome}
            detail={textTrainingOutcomeDetail}
            successLabel={t("chat.trainingLearned")}
            errorLabel={t("chat.trainingErrorLabel")}
            cancelledLabel={t("chat.trainingAborted")}
          />
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
      {canShowEvidenceUi ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 px-2 text-xs text-[var(--color-muted)]">
          {queryRunId && sources.length > 0 ? (
            <ChatFeedbackControls feedbackValue={feedbackValue} feedbackLoading={feedbackLoading} onSendFeedback={sendFeedback} t={t} />
          ) : null}
          <button
            type="button"
            onClick={() => setSourceModalOpen(true)}
            className="rounded-full border border-[var(--color-border)] bg-transparent px-2.5 py-1 font-semibold text-[var(--color-muted)] transition hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
          >
            {t("chat.sourceFallback")}
          </button>
        </div>
      ) : null}
      {sourceModalOpen ? (
        <ChatSourceModal
          sourceTab={sourceTab}
          setSourceTab={setSourceTab}
          onClose={() => setSourceModalOpen(false)}
          t={t}
          locale={locale}
          timezone={settings?.timezone}
          dateFormat={settings?.date_format}
          timeFormat={settings?.time_format}
          answerMode={answerMode}
          evidence={evidence}
          citedSourceIds={citedSourceIds}
          promptContext={promptContext}
          sources={sources}
          contextBlocks={contextBlocks}
          matchedChunks={matchedChunks}
          citations={citations}
          debugPayload={debug}
          sourceLoadingId={sourceLoadingId}
          onDownloadSource={downloadSource}
          context={promptContextDetail}
        />
      ) : null}
    </div>
  );
}

function buildPromptContextDetail({
  promptContext,
  encodedPromptContext,
  sources,
  question,
}: {
  promptContext?: Record<string, unknown>;
  encodedPromptContext?: string;
  sources: ChatSource[];
  question?: string;
}) {
  const fallbackLlmContextFromSources = sources
    .map((source) => String(source.snippet || source.title || "").trim())
    .filter(Boolean)
    .join("\n\n---\n\n")
    .trim();
  return {
    infoPrompt: String(promptContext?.informational_prompt || "").trim(),
    qaContext: String(promptContext?.qa_context || "").trim(),
    latestQuestion: String(promptContext?.latest_question || question || "").trim(),
    retrievalContext: String(promptContext?.retrieval_context || "").trim(),
    llmContextText: String(promptContext?.llm_context_text || fallbackLlmContextFromSources || "").trim(),
    encodedLlmContextText: String(promptContext?.encoded_llm_context_text || encodedPromptContext || "").trim(),
    piiApplied: typeof promptContext?.pii_applied === "boolean" ? promptContext.pii_applied : null,
    piiReason: String(promptContext?.pii_reason || "").trim(),
    rawContextSentToLlm: String(promptContext?.raw_context_sent_to_llm || "").trim(),
    rawInputsBeforePii:
      promptContext?.raw_inputs_before_pii && typeof promptContext.raw_inputs_before_pii === "object"
        ? (promptContext.raw_inputs_before_pii as Record<string, unknown>)
        : null,
    contextComponents:
      promptContext?.context_components && typeof promptContext.context_components === "object"
        ? (promptContext.context_components as Record<string, unknown>)
        : null,
    answerInformationSources: Array.isArray(promptContext?.answer_information_sources)
      ? (promptContext.answer_information_sources as Array<Record<string, unknown>>)
      : [],
    latestHits: Array.isArray(promptContext?.latest_hits) ? promptContext.latest_hits : [],
    indexDebug: promptContext?.index_debug && typeof promptContext.index_debug === "object" ? promptContext.index_debug : null,
  };
}

export default memo(ChatMessageInner);
