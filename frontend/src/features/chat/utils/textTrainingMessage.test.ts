import { describe, expect, it } from "vitest";

import type { ChatMessageType } from "../types";
import {
  patchLastPendingTextTrainingCharacterCount,
  patchLastPendingTextTrainingMessage,
} from "./textTrainingMessage";

describe("patchLastPendingTextTrainingCharacterCount", () => {
  it("a függő tanítási user üzenetre menti a karakterszámot", () => {
    const messages: ChatMessageType[] = [
      { role: "user", text: "training.txt", excludeFromAiContext: true, textTrainingPending: true },
    ];

    const next = patchLastPendingTextTrainingCharacterCount(messages, 89002);

    expect(next[0].textTrainingCharacterCount).toBe(89002);
  });
});

describe("patchLastPendingTextTrainingMessage", () => {
  it("megszakított állapotot ír a legutolsó függő tanítási user üzenetre", () => {
    const messages: ChatMessageType[] = [
      { role: "assistant", text: "Szia" },
      { role: "user", text: "training.txt", excludeFromAiContext: true, textTrainingPending: true },
    ];

    const next = patchLastPendingTextTrainingMessage(messages, {
      textTrainingOutcome: "cancelled",
      textTrainingOutcomeDetail: "Megszakítva",
    });

    expect(next[1]).toMatchObject({
      textTrainingPending: false,
      textTrainingOutcome: "cancelled",
      textTrainingOutcomeDetail: "Megszakítva",
    });
  });
});
