import { sanitizeMessage } from "../../../../utils/sanitize";
import type { RestoredPiiSpan } from "./chatMessageTypes";
import { renderTextWithRestoredHighlights } from "../../utils/chatMessageFormatting";

type ChatMessageBubbleProps = {
  isUser: boolean;
  isTrainingUserBubble: boolean;
  isTrainingStatus: boolean;
  text: string;
  progressPercent?: number | null;
  restoredPiiSpans: RestoredPiiSpan[];
  trainingContentLabel?: string;
};

export default function ChatMessageBubble({
  isUser,
  isTrainingUserBubble,
  isTrainingStatus,
  text,
  progressPercent,
  restoredPiiSpans,
  trainingContentLabel,
}: ChatMessageBubbleProps) {
  return (
    <div
      className={`whitespace-pre-wrap break-words px-4 py-2 text-sm leading-relaxed ${
        isTrainingStatus
          ? "rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)]"
          : isTrainingUserBubble
            ? "chat-training-user-bubble rounded-3xl"
            : isUser
              ? "rounded-3xl bg-[var(--color-primary)] text-[var(--color-on-primary)]"
              : "my-2 rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)]"
      }`}
    >
      {!isUser && !isTrainingStatus ? (
        renderTextWithRestoredHighlights(text, restoredPiiSpans)
      ) : isTrainingUserBubble && trainingContentLabel ? (
        <>
          <span className="font-medium text-[var(--color-muted)]">{trainingContentLabel} </span>
          {sanitizeMessage(text)}
        </>
      ) : (
        sanitizeMessage(text)
      )}
      {typeof progressPercent === "number" ? (
        <div className="mt-2 h-1 w-[30px] overflow-hidden rounded-full bg-[var(--color-border)]">
          <div
            className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
            style={{ width: `${Math.max(0, Math.min(100, Math.round(progressPercent)))}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
