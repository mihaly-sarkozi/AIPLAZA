import type { ChatMessageType } from "../types";

export type TextTrainingOutcome = "success" | "error" | "cancelled";

export function patchLastPendingTextTrainingCharacterCount(
  messages: ChatMessageType[],
  characterCount: number
): ChatMessageType[] {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.textTrainingPending && !message.textTrainingOutcome) {
      const next = [...messages];
      next[index] = { ...message, textTrainingCharacterCount: characterCount };
      return next;
    }
  }
  return messages;
}

export function findLastPendingTextTrainingMessage(messages: ChatMessageType[]): ChatMessageType | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.textTrainingPending && !message.textTrainingOutcome) {
      return message;
    }
  }
  return undefined;
}

export function patchLastPendingTextTrainingMessage(
  messages: ChatMessageType[],
  patch: {
    textTrainingOutcome: TextTrainingOutcome;
    textTrainingOutcomeDetail: string;
  }
): ChatMessageType[] {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.textTrainingPending) {
      const next = [...messages];
      next[index] = {
        ...next[index],
        textTrainingPending: false,
        textTrainingOutcome: patch.textTrainingOutcome,
        textTrainingOutcomeDetail: patch.textTrainingOutcomeDetail,
      };
      return next;
    }
  }
  return messages;
}
