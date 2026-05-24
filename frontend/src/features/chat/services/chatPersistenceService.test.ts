import { beforeEach, describe, expect, it } from "vitest";

import {
  chatLegacySessionKey,
  chatPersistKey,
  clearChatContextNotice,
  clearLegacyChatSession,
  clearLocalChatHistory,
  loadChatContextNoticeFallback,
  loadPersistedChatSession,
  MAX_PERSISTED_CHARS,
  MAX_PERSISTED_MESSAGES,
  saveChatContextNotice,
  savePersistedChatSession,
  sanitizePersistedMessages,
} from "./chatPersistenceService";
import type { PersistedChatSession } from "../types";

describe("chatPersistenceService", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("persists chat history under a per-user non-auth key", () => {
    const payload: PersistedChatSession = {
      messages: [{ role: "user", text: "sensitive chat text" }],
      contextNotice: null,
      draft: "",
    };

    savePersistedChatSession(123, payload);

    expect(localStorage.getItem(chatPersistKey(123))).toContain("sensitive chat text");
    expect(localStorage.getItem("token")).toBeNull();
    expect(sessionStorage.getItem("token")).toBeNull();
  });

  it("loads and trims persisted messages", () => {
    const payload: PersistedChatSession = {
      messages: Array.from({ length: 105 }, (_, index) => ({ role: "user", text: String(index) })),
      contextNotice: null,
      draft: "",
    };
    savePersistedChatSession(123, payload);

    const loaded = loadPersistedChatSession(123);

    expect(loaded?.messages).toHaveLength(MAX_PERSISTED_MESSAGES);
    expect(loaded?.messages?.[0]?.text).toBe("5");
  });

  it("enforces total persisted character budget", () => {
    const messages = [
      { role: "user", text: "x".repeat(MAX_PERSISTED_CHARS + 10) },
      { role: "assistant", text: "should not fit" },
    ];

    const sanitized = sanitizePersistedMessages(messages);

    expect(sanitized.map((message) => message.text).join("")).toHaveLength(MAX_PERSISTED_CHARS);
    expect(sanitized).toHaveLength(1);
  });

  it("drops debug and prompt context from persisted messages", () => {
    savePersistedChatSession(123, {
      messages: [
        {
          role: "assistant",
          text: "answer",
          debug: { prompt: "secret debug" },
          promptContext: { raw: "secret prompt" },
          encodedPromptContext: "encoded secret",
          restoredPiiSpans: [{ start: 0, end: 1, value: "secret" }],
        },
      ],
      contextNotice: null,
      draft: "",
    });

    const raw = localStorage.getItem(chatPersistKey(123)) ?? "";
    expect(raw).not.toContain("secret debug");
    expect(raw).not.toContain("secret prompt");
    expect(raw).not.toContain("encoded secret");
    expect(raw).not.toContain("restoredPiiSpans");
  });

  it("returns null for malformed persisted JSON", () => {
    localStorage.setItem(chatPersistKey(123), "{bad json");
    expect(loadPersistedChatSession(123)).toBeNull();
  });

  it("migrates legacy sessionStorage chat history once", () => {
    sessionStorage.setItem(chatLegacySessionKey("u1"), JSON.stringify({ messages: [], contextNotice: null, draft: "hello" }));

    expect(loadPersistedChatSession("u1")?.draft).toBe("hello");
    expect(localStorage.getItem(chatPersistKey("u1"))).toContain("hello");
    expect(sessionStorage.getItem(chatLegacySessionKey("u1"))).toBeNull();
  });

  it("stores and clears context notice separately", () => {
    saveChatContextNotice("notice");
    expect(loadChatContextNoticeFallback()).toBe("notice");

    clearChatContextNotice();
    expect(loadChatContextNoticeFallback()).toBeNull();
  });

  it("clears legacy session key without touching persisted local chat history", () => {
    localStorage.setItem(chatPersistKey(123), "persisted");
    sessionStorage.setItem(chatLegacySessionKey(123), "legacy");

    clearLegacyChatSession(123);

    expect(sessionStorage.getItem(chatLegacySessionKey(123))).toBeNull();
    expect(localStorage.getItem(chatPersistKey(123))).toBe("persisted");
  });

  it("clears all local chat history for a user", () => {
    localStorage.setItem(chatPersistKey(123), "persisted");
    sessionStorage.setItem(chatLegacySessionKey(123), "legacy");
    saveChatContextNotice("notice");

    clearLocalChatHistory(123);

    expect(localStorage.getItem(chatPersistKey(123))).toBeNull();
    expect(sessionStorage.getItem(chatLegacySessionKey(123))).toBeNull();
    expect(loadChatContextNoticeFallback()).toBeNull();
  });
});
