import type { RefObject } from "react";

import type { ChatComposerMode } from "./chatComposerTypes";

type ChatComposerActionsProps = {
  chatMode: ChatComposerMode;
  loading: boolean;
  messagesLength: number;
  contextNotice: string | null;
  trainingOperationRunning: boolean;
  pendingTrainingConfirmation: boolean;
  trainFileRef: RefObject<HTMLInputElement | null>;
  clearHistory: () => void;
  exportChatProcess: () => void;
  send: () => void;
  onSubmitTextTraining: () => void;
  t: (key: string) => string;
};

function IconButton({
  label,
  title = label,
  disabled,
  onClick,
  children,
  primary = false,
}: {
  label: string;
  title?: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
  primary?: boolean;
}) {
  const className = primary
    ? `pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold leading-none transition ${
        disabled ? "cursor-not-allowed bg-[var(--color-border)] text-[var(--color-muted)]" : "bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
      }`
    : `pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border transition ${
        disabled
          ? "cursor-not-allowed border-[var(--color-border)] text-[var(--color-muted)] opacity-50"
          : "border-[var(--color-border)] bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
      }`;

  return (
    <button type="button" onClick={onClick} disabled={disabled} className={className} aria-label={label} title={title}>
      {children}
    </button>
  );
}

export default function ChatComposerActions({
  chatMode,
  loading,
  messagesLength,
  contextNotice,
  trainingOperationRunning,
  pendingTrainingConfirmation,
  trainFileRef,
  clearHistory,
  exportChatProcess,
  send,
  onSubmitTextTraining,
  t,
}: ChatComposerActionsProps) {
  const trainingDisabled = trainingOperationRunning || pendingTrainingConfirmation;
  const sendDisabled = loading || (chatMode === "train" && trainingDisabled);
  const exportDisabled = messagesLength === 0 && !contextNotice;

  return (
    <div className="pointer-events-none absolute bottom-3 right-3 z-10 flex items-center gap-2">
      {chatMode !== "train" && messagesLength > 0 ? (
        <IconButton label={t("chat.newChat")} onClick={clearHistory}>
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M6.5 4.5h8l3 3v11c0 .6-.4 1-1 1h-10c-.6 0-1-.4-1-1v-13c0-.6.4-1 1-1Z"
              fill="white"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
            <path
              d="M14.5 4.5v3h3M9 15.5l.5-2.2 5.7-5.7c.5-.5 1.3-.5 1.8 0s.5 1.3 0 1.8l-5.7 5.7-2.3.4Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </IconButton>
      ) : null}
      {chatMode === "train" ? (
        <IconButton label={t("chat.selectTrainingFile")} disabled={trainingDisabled} onClick={() => trainFileRef.current?.click()}>
          <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 16V5m0 0 4 4m-4-4-4 4M5 16.5V18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2v-1.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </IconButton>
      ) : null}
      <IconButton label="Folyamat exportálása (.txt)" disabled={exportDisabled} onClick={exportChatProcess}>
        <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 4.5h11l3 3V19a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 19V6a1.5 1.5 0 0 1 1-1.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          <path d="M9 4.5V9h6V4.5M8 14h8M8 17h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </IconButton>
      <IconButton label={chatMode === "train" ? t("chat.startTraining") : t("chat.sendQuestion")} disabled={sendDisabled} onClick={chatMode === "train" ? onSubmitTextTraining : send} primary>
        ↑
      </IconButton>
    </div>
  );
}
