import { describe, expect, it } from "vitest";

import { buildConversationHistory, buildRetrievalHistory, isClearHistoryCommand, trimToLastN } from "./chatHistory";
import type { ChatMessageType } from "../types";

describe("chatHistory helpers", () => {
  it("trims messages to the last N entries", () => {
    expect(trimToLastN([{ role: "user", text: "1" }, { role: "assistant", text: "2" }], 1)).toEqual([
      { role: "assistant", text: "2" },
    ]);
  });

  it("builds sanitized conversation history from user and assistant messages", () => {
    const messages: ChatMessageType[] = [
      { role: "system", text: "hidden" },
      { role: "user", text: "visible", aiContextContent: "encoded user" },
      { role: "assistant", text: "answer" },
    ];

    expect(buildConversationHistory(messages)).toEqual([
      { role: "user", content: "encoded user" },
      { role: "assistant", content: "answer" },
    ]);
  });

  it("excludes training flow user input from AI context", () => {
    const messages: ChatMessageType[] = [
      { role: "user", text: "training text" },
      { role: "training-status", text: "Tanitas indul" },
      { role: "assistant", text: "normal answer" },
    ];

    expect(buildConversationHistory(messages)).toEqual([{ role: "assistant", content: "normal answer" }]);
  });

  it("builds deduplicated retrieval history from recent assistant context blocks", () => {
    const longSnippet = "x".repeat(400);
    const messages: ChatMessageType[] = [
      { role: "assistant", text: "old", contextBlocks: [{ snippet: "same" }] },
      {
        role: "assistant",
        text: "new",
        contextBlocks: [{ snippet: "same" }, { text: longSnippet }],
      },
    ];

    expect(buildRetrievalHistory(messages)).toEqual(["same", `${"x".repeat(320)}...`]);
  });

  it("recognizes Hungarian clear history commands without accents", () => {
    expect(isClearHistoryCommand("előzmények törlése")).toBe(true);
    expect(isClearHistoryCommand("Töröld az előzményt")).toBe(true);
    expect(isClearHistoryCommand("normal kerdes")).toBe(false);
  });
});
