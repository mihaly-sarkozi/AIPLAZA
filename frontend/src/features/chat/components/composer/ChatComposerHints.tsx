import type { ComposerUsage, KnowledgeBaseOption, ChatComposerMode } from "./chatComposerTypes";

type ChatComposerHintsProps = {
  chatMode: ChatComposerMode;
  setChatMode: (mode: ChatComposerMode) => void;
  loading: boolean;
  trainingOperationRunning: boolean;
  pendingTrainingConfirmation: boolean;
  selectedTopKbUuid: string;
  selectedTopKbLabel: string;
  selectableChatKbList: KnowledgeBaseOption[];
  trainableKbList: KnowledgeBaseOption[];
  composerUsage: ComposerUsage;
  setSelectedTrainKbUuid: (value: string) => void;
  setSelectedChatKbUuid: (value: string) => void;
  t: (key: string) => string;
};

export default function ChatComposerHints({
  chatMode,
  setChatMode,
  loading,
  trainingOperationRunning,
  pendingTrainingConfirmation,
  selectedTopKbUuid,
  selectedTopKbLabel,
  selectableChatKbList,
  trainableKbList,
  composerUsage,
  setSelectedTrainKbUuid,
  setSelectedChatKbUuid,
  t,
}: ChatComposerHintsProps) {
  const kbOptions = chatMode === "train" ? trainableKbList : selectableChatKbList;
  const canTrain = trainableKbList.length > 0;

  return (
    <div className="absolute bottom-3 left-3 right-14 flex items-center gap-2 overflow-visible">
      <div className="relative rounded-full bg-neutral-700 pl-1.5 pr-4">
        <select
          value={chatMode}
          onChange={(event) => setChatMode(event.target.value === "train" ? "train" : "query")}
          className="!h-8 !w-auto appearance-none !rounded-full !border-0 !bg-transparent !py-0 pl-0 pr-7 text-xs font-medium leading-none !text-gray-100 !shadow-none focus:!border-0 focus:!bg-transparent focus:!text-gray-100 focus:!shadow-none focus:!ring-0 active:!bg-transparent"
          aria-label={t("chat.chatModeLabel")}
        >
          <option value="query">{t("chat.modeQuery")}</option>
          {canTrain ? <option value="train">{t("chat.modeTrain")}</option> : null}
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
          {kbOptions.map((kb) => (
            <option key={kb.uuid} value={kb.uuid}>
              {kb.name}
            </option>
          ))}
        </select>
      </div>
      {composerUsage ? (
        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-muted)]" title={composerUsage.title} aria-label={composerUsage.label}>
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
  );
}
