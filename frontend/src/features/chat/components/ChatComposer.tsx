import type { DragEvent, KeyboardEvent, RefObject } from "react";

type KnowledgeBaseOption = {
  uuid: string;
  name: string;
};

type ComposerUsage = {
  percent: number;
  label: string;
  title: string;
} | null;

type ChatComposerProps = {
  chatMode: "query" | "train";
  setChatMode: (mode: "query" | "train") => void;
  dragOverTrainFile: boolean;
  setDragOverTrainFile: (value: boolean) => void;
  inputDraft: string;
  setInputDraft: (value: string) => void;
  loading: boolean;
  messagesLength: number;
  contextNotice: string | null;
  trainingOperationRunning: boolean;
  pendingTrainingConfirmation: boolean;
  selectedTopKbUuid: string;
  selectedTopKbLabel: string;
  selectableChatKbList: KnowledgeBaseOption[];
  trainableKbList: KnowledgeBaseOption[];
  composerUsage: ComposerUsage;
  inputRef: RefObject<HTMLInputElement | null>;
  trainFileRef: RefObject<HTMLInputElement | null>;
  onSelectTrainingFile: (file: File | null) => void;
  clearHistory: () => void;
  exportChatProcess: () => void;
  send: () => void;
  onSubmitTextTraining: () => void;
  setSelectedTrainKbUuid: (value: string) => void;
  setSelectedChatKbUuid: (value: string) => void;
  t: (key: string) => string;
};

export default function ChatComposer({
  chatMode,
  setChatMode,
  dragOverTrainFile,
  setDragOverTrainFile,
  inputDraft,
  setInputDraft,
  loading,
  messagesLength,
  contextNotice,
  trainingOperationRunning,
  pendingTrainingConfirmation,
  selectedTopKbUuid,
  selectedTopKbLabel,
  selectableChatKbList,
  trainableKbList,
  composerUsage,
  inputRef,
  trainFileRef,
  onSelectTrainingFile,
  clearHistory,
  exportChatProcess,
  send,
  onSubmitTextTraining,
  setSelectedTrainKbUuid,
  setSelectedChatKbUuid,
  t,
}: ChatComposerProps) {
  const onComposerDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (chatMode !== "train") return;
    event.preventDefault();
    event.stopPropagation();
    setDragOverTrainFile(true);
  };
  const onComposerDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (chatMode !== "train") return;
    event.preventDefault();
    event.stopPropagation();
    setDragOverTrainFile(false);
  };
  const onComposerDrop = (event: DragEvent<HTMLDivElement>) => {
    if (chatMode !== "train") return;
    event.preventDefault();
    event.stopPropagation();
    setDragOverTrainFile(false);
    onSelectTrainingFile(event.dataTransfer?.files?.[0] ?? null);
  };
  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (chatMode === "train") {
        onSubmitTextTraining();
      } else {
        send();
      }
    }
  };

  return (
    <>
      <input
        ref={trainFileRef}
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
        className="hidden"
        onChange={(e) => onSelectTrainingFile(e.target.files?.[0] ?? null)}
      />
      <div className="shrink-0 w-full bg-[var(--color-background)] px-4 pt-[18px] pb-2">
        <div
          className={`relative mx-auto h-28 max-w-3xl overflow-hidden rounded-[32px] border bg-[var(--color-card)] ${
            chatMode === "train" && dragOverTrainFile ? "border-[var(--color-primary)]" : "border-[var(--color-border)]"
          }`}
          onDragOver={onComposerDragOver}
          onDragLeave={onComposerDragLeave}
          onDrop={onComposerDrop}
        >
          <div className="pointer-events-none absolute bottom-3 right-3 z-10 flex items-center gap-2">
            {chatMode !== "train" && messagesLength > 0 ? (
              <button
                type="button"
                onClick={clearHistory}
                className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] bg-transparent text-[var(--color-muted)] transition hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                aria-label={t("chat.newChat")}
                title={t("chat.newChat")}
              >
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
              </button>
            ) : null}
            {chatMode === "train" ? (
              <button
                type="button"
                onClick={() => trainFileRef.current?.click()}
                disabled={trainingOperationRunning || pendingTrainingConfirmation}
                className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border transition ${
                  trainingOperationRunning || pendingTrainingConfirmation
                    ? "cursor-not-allowed border-[var(--color-border)] text-[var(--color-muted)] opacity-50"
                    : "border-[var(--color-border)] bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                }`}
                aria-label={t("chat.selectTrainingFile")}
                title={t("chat.selectTrainingFile")}
              >
                <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 16V5m0 0 4 4m-4-4-4 4M5 16.5V18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2v-1.5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            ) : null}
            <button
              type="button"
              onClick={exportChatProcess}
              disabled={messagesLength === 0 && !contextNotice}
              className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border transition ${
                messagesLength === 0 && !contextNotice
                  ? "cursor-not-allowed border-[var(--color-border)] text-[var(--color-muted)] opacity-50"
                  : "border-[var(--color-border)] bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
              }`}
              aria-label="Folyamat exportálása (.txt)"
              title="Folyamat exportálása (.txt)"
            >
              <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M5 4.5h11l3 3V19a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 19V6a1.5 1.5 0 0 1 1-1.5Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="M9 4.5V9h6V4.5M8 14h8M8 17h5"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <button
              type="button"
              onClick={chatMode === "train" ? onSubmitTextTraining : send}
              disabled={loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))}
              className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold leading-none transition ${
                loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))
                  ? "cursor-not-allowed bg-[var(--color-border)] text-[var(--color-muted)]"
                  : "bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
              }`}
              aria-label={chatMode === "train" ? t("chat.startTraining") : t("chat.sendQuestion")}
            >
              ↑
            </button>
          </div>
          <input
            type="text"
            ref={inputRef}
            value={inputDraft}
            onChange={(e) => setInputDraft(e.target.value)}
            onKeyDown={onInputKeyDown}
            className="chat-question-input chat-composer-input w-full h-14 min-h-0 overflow-hidden bg-transparent text-[var(--color-foreground)] rounded-[999px] box-border text-base leading-none !py-0 !pl-5 pr-5"
            placeholder={chatMode === "train" ? t("chat.trainPlaceholder") : t("chat.queryPlaceholder")}
            disabled={loading || (chatMode === "train" && trainingOperationRunning)}
          />
          <div className="absolute bottom-3 left-3 right-14 flex items-center gap-2 overflow-visible">
            <div className="relative rounded-full bg-neutral-700 pl-1.5 pr-4">
              <select
                value={chatMode}
                onChange={(event) => setChatMode(event.target.value === "train" ? "train" : "query")}
                className="!h-8 !w-auto appearance-none !rounded-full !border-0 !bg-transparent !py-0 pl-0 pr-7 text-xs font-medium leading-none !text-gray-100 !shadow-none focus:!border-0 focus:!bg-transparent focus:!text-gray-100 focus:!shadow-none focus:!ring-0 active:!bg-transparent"
                aria-label={t("chat.chatModeLabel")}
              >
                <option value="query">{t("chat.modeQuery")}</option>
                <option value="train">{t("chat.modeTrain")}</option>
              </select>
              <span className="pointer-events-none absolute right-3 top-1/2 h-1.5 w-1.5 -translate-y-[65%] rotate-45 border-b border-r border-white/80" />
            </div>
            <div className="relative inline-flex min-w-0 items-center">
              <span className="max-w-[240px] truncate text-xs font-bold leading-5 text-[var(--color-foreground)]">{selectedTopKbLabel}</span>
              <span className="ml-[5px] h-1.5 w-1.5 -translate-y-[1px] rotate-45 border-b border-r border-[var(--color-muted)]" />
              <select
                value={selectedTopKbUuid}
                onChange={(event) => {
                  if (chatMode === "train") {
                    setSelectedTrainKbUuid(event.target.value);
                  } else {
                    setSelectedChatKbUuid(event.target.value);
                  }
                }}
                className="absolute inset-0 !h-full !w-full cursor-pointer appearance-none !rounded-none !border-0 !bg-transparent !p-0 opacity-0 !shadow-none focus:!border-0 focus:!shadow-none focus:!ring-0"
                disabled={loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))}
                aria-label={t("chat.kbSelectorLabel")}
              >
                {chatMode === "query" && selectableChatKbList.length > 1 ? <option value="">{t("chat.allKbs")}</option> : null}
                {(chatMode === "train" ? trainableKbList : selectableChatKbList).map((kb) => (
                  <option key={kb.uuid} value={kb.uuid}>
                    {kb.name}
                  </option>
                ))}
              </select>
            </div>
            {composerUsage ? (
              <div
                className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-muted)]"
                title={composerUsage.title}
                aria-label={composerUsage.label}
              >
                <svg className="h-5 w-5 -rotate-90" viewBox="0 0 20 20" aria-hidden="true">
                  <circle cx="10" cy="10" r="7" fill="none" stroke="var(--color-border)" strokeWidth="2.5" />
                  <circle
                    cx="10"
                    cy="10"
                    r="7"
                    fill="none"
                    stroke="var(--color-primary)"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeDasharray={`${(composerUsage.percent / 100) * 43.98} 43.98`}
                  />
                </svg>
                <span className="max-w-[160px] truncate">{composerUsage.label}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}
