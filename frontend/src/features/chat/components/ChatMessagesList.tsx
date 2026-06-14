import type { RefObject } from "react";

import type { ChatMessageType, FileCountingProgress } from "../types";
import ChatMessage from "./ChatMessage";

type ChatMessagesListProps = {
  contextNotice: string | null;
  messages: ChatMessageType[];
  loading: boolean;
  fileCountingProgress: FileCountingProgress | null;
  activeTrainingTitle: string | null;
  displayedTrainingProgress: number;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  emptyStateKey?: string;
  t: (key: string) => string;
};

export default function ChatMessagesList({
  contextNotice,
  messages,
  loading,
  fileCountingProgress,
  activeTrainingTitle,
  displayedTrainingProgress,
  messagesEndRef,
  emptyStateKey = "chat.emptyState",
  t,
}: ChatMessagesListProps) {
  let activePendingTrainingIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index];
    if (msg?.textTrainingPending && !msg.textTrainingOutcome) {
      activePendingTrainingIndex = index;
      break;
    }
  }

  return (
    <>
      {contextNotice ? (
        <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
          <div className="flex w-full justify-start">
            <ChatMessage role="assistant" text={contextNotice} />
          </div>
        </div>
      ) : null}
      {messages.length > 0 ? (
        <div className="space-y-1">
          {messages.map((msg, index) => (
            <div key={`${msg.role}-${index}`} className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
              <div className={`flex w-full ${msg.role === "user" || msg.role === "training-status" ? "justify-end" : "justify-start"}`}>
                <ChatMessage
                  role={msg.role}
                  text={msg.text}
                  question={msg.question}
                  queryRunId={msg.queryRunId}
                  answerMode={msg.answerMode}
                  answerSource={msg.answerSource}
                  confidence={msg.confidence}
                  evidence={msg.evidence}
                  citedClaimIds={msg.citedClaimIds}
                  citedSentenceIds={msg.citedSentenceIds}
                  citedSourceIds={msg.citedSourceIds}
                  queryProfile={msg.queryProfile}
                  matchedChunks={msg.matchedChunks}
                  claims={msg.claims}
                  contextBlocks={msg.contextBlocks}
                  citations={msg.citations}
                  actionLabel={msg.actionLabel}
                  actionHref={msg.actionHref}
                  progressPercent={msg.progressPercent}
                  textTrainingPending={msg.textTrainingPending}
                  textTrainingInProgress={index === activePendingTrainingIndex && activeTrainingTitle !== null}
                  textTrainingProgressPercent={displayedTrainingProgress}
                  textTrainingOutcome={msg.textTrainingOutcome}
                  textTrainingOutcomeDetail={msg.textTrainingOutcomeDetail}
                  excludeFromAiContext={msg.excludeFromAiContext}
                  sources={msg.sources}
                  promptContext={msg.promptContext}
                  debug={msg.debug}
                  encodedPromptContext={msg.encodedPromptContext}
                  restoredPiiSpans={msg.restoredPiiSpans}
                />
              </div>
            </div>
          ))}
          {fileCountingProgress ? (
            <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
              <div className="flex w-full items-center justify-end gap-2">
                <span className="text-xs font-medium text-[var(--color-muted)]">Beolvasás</span>
                <div className="mr-4 h-1 w-[120px] overflow-hidden rounded-full bg-[var(--color-border)]">
                  <div
                    className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
                    style={{ width: `${Math.max(0, Math.min(100, Math.round(fileCountingProgress.percent)))}%` }}
                  />
                </div>
              </div>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>
      ) : null}

      {messages.length === 0 ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-[var(--color-muted)] text-sm leading-6 pointer-events-none">
          <div className="max-w-lg whitespace-pre-line">{t(emptyStateKey)}</div>
        </div>
      ) : null}

      {loading && (
        <div className="mx-auto flex max-w-3xl justify-start pt-2 pb-2">
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] px-4 py-2 text-[var(--color-muted)] animate-pulse">
            ...
          </div>
        </div>
      )}
    </>
  );
}
