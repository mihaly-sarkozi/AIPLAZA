import type { KeyboardEvent } from "react";

import type { ChatComposerInputProps } from "./chatComposerTypes";

export default function ChatComposerTextarea({
  chatMode,
  inputDraft,
  setInputDraft,
  loading,
  trainingOperationRunning,
  inputRef,
  onSubmitTextTraining,
  send,
  t,
}: ChatComposerInputProps) {
  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (chatMode === "train") {
      onSubmitTextTraining();
    } else {
      send();
    }
  };

  return (
    <input
      type="text"
      ref={inputRef}
      value={inputDraft}
      onChange={(event) => setInputDraft(event.target.value)}
      onKeyDown={onInputKeyDown}
      className="chat-question-input chat-composer-input w-full h-14 min-h-0 overflow-hidden bg-transparent text-[var(--color-foreground)] rounded-[999px] box-border text-base leading-none !py-0 !pl-5 pr-5"
      placeholder={chatMode === "train" ? t("chat.trainPlaceholder") : t("chat.queryPlaceholder")}
      disabled={loading || (chatMode === "train" && trainingOperationRunning)}
    />
  );
}
