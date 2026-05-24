import type { DragEvent, RefObject } from "react";

import ChatComposerActions from "./composer/ChatComposerActions";
import ChatComposerHints from "./composer/ChatComposerHints";
import ChatComposerTextarea from "./composer/ChatComposerTextarea";
import type { ChatComposerMode, ComposerUsage, KnowledgeBaseOption } from "./composer/chatComposerTypes";
import TrainingUploadControls from "./composer/TrainingUploadControls";

type ChatComposerProps = {
  chatMode: ChatComposerMode;
  setChatMode: (mode: ChatComposerMode) => void;
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
  return (
    <>
      <TrainingUploadControls trainFileRef={trainFileRef} onSelectTrainingFile={onSelectTrainingFile} />
      <div className="shrink-0 w-full bg-[var(--color-background)] px-4 pt-[18px] pb-2">
        <div
          className={`relative mx-auto h-28 max-w-3xl overflow-hidden rounded-[32px] border bg-[var(--color-card)] ${
            chatMode === "train" && dragOverTrainFile ? "border-[var(--color-primary)]" : "border-[var(--color-border)]"
          }`}
          onDragOver={onComposerDragOver}
          onDragLeave={onComposerDragLeave}
          onDrop={onComposerDrop}
        >
          <ChatComposerActions
            chatMode={chatMode}
            loading={loading}
            messagesLength={messagesLength}
            contextNotice={contextNotice}
            trainingOperationRunning={trainingOperationRunning}
            pendingTrainingConfirmation={pendingTrainingConfirmation}
            trainFileRef={trainFileRef}
            clearHistory={clearHistory}
            exportChatProcess={exportChatProcess}
            send={send}
            onSubmitTextTraining={onSubmitTextTraining}
            t={t}
          />
          <ChatComposerTextarea
            chatMode={chatMode}
            inputDraft={inputDraft}
            setInputDraft={setInputDraft}
            loading={loading}
            trainingOperationRunning={trainingOperationRunning}
            pendingTrainingConfirmation={pendingTrainingConfirmation}
            inputRef={inputRef}
            onSubmitTextTraining={onSubmitTextTraining}
            send={send}
            t={t}
          />
          <ChatComposerHints
            chatMode={chatMode}
            setChatMode={setChatMode}
            loading={loading}
            trainingOperationRunning={trainingOperationRunning}
            pendingTrainingConfirmation={pendingTrainingConfirmation}
            selectedTopKbUuid={selectedTopKbUuid}
            selectedTopKbLabel={selectedTopKbLabel}
            selectableChatKbList={selectableChatKbList}
            trainableKbList={trainableKbList}
            composerUsage={composerUsage}
            setSelectedTrainKbUuid={setSelectedTrainKbUuid}
            setSelectedChatKbUuid={setSelectedChatKbUuid}
            t={t}
          />
        </div>
      </div>
    </>
  );
}
