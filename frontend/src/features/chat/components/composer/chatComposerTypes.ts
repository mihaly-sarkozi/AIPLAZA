import type { RefObject } from "react";

export type KnowledgeBaseOption = {
  uuid: string;
  name: string;
};

export type ComposerUsage = {
  percent: number;
  label: string;
  title: string;
} | null;

export type ChatComposerMode = "query" | "train";

export type ChatComposerSharedProps = {
  chatMode: ChatComposerMode;
  loading: boolean;
  trainingOperationRunning: boolean;
  pendingTrainingConfirmation: boolean;
  t: (key: string) => string;
};

export type ChatComposerInputProps = ChatComposerSharedProps & {
  inputDraft: string;
  setInputDraft: (value: string) => void;
  inputRef: RefObject<HTMLInputElement | null>;
  onSubmitTextTraining: () => void;
  send: () => void;
};
