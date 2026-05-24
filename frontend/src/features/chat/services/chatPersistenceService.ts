import type { ChatMessageType, PersistedChatSession } from "../types";

const CHAT_CONTEXT_STORAGE_KEY = "aiplaza_chat_context_notice";
const CHAT_PERSIST_PREFIX = "aiplaza_chat_persist_v2:";
const CHAT_SESSION_LEGACY_PREFIX = "aiplaza_chat_session_v1:";
export const MAX_PERSISTED_MESSAGES = 100;
export const MAX_PERSISTED_CHARS = 100_000;

export function chatPersistKey(userId: number | string): string {
  return `${CHAT_PERSIST_PREFIX}${String(userId)}`;
}

export function chatLegacySessionKey(userId: number | string): string {
  return `${CHAT_SESSION_LEGACY_PREFIX}${String(userId)}`;
}

export function saveChatContextNotice(contextNotice: string | null): void {
  try {
    if (contextNotice) {
      localStorage.setItem(CHAT_CONTEXT_STORAGE_KEY, contextNotice);
    } else {
      localStorage.removeItem(CHAT_CONTEXT_STORAGE_KEY);
    }
  } catch {
    // storage optional
  }
}

export function clearChatContextNotice(): void {
  try {
    localStorage.removeItem(CHAT_CONTEXT_STORAGE_KEY);
  } catch {
    // storage optional
  }
}

export function clearLegacyChatSession(userId: number | string | null | undefined): void {
  if (userId == null) return;
  try {
    sessionStorage.removeItem(chatLegacySessionKey(userId));
  } catch {
    // storage optional
  }
}

function truncateText(value: unknown, remainingChars: { value: number }): string | undefined {
  const text = typeof value === "string" ? value : "";
  if (!text || remainingChars.value <= 0) return undefined;
  const next = text.slice(0, remainingChars.value);
  remainingChars.value -= next.length;
  return next;
}

export function sanitizePersistedMessages(messages: unknown): ChatMessageType[] {
  if (!Array.isArray(messages)) return [];
  const remainingChars = { value: MAX_PERSISTED_CHARS };
  const sanitized: ChatMessageType[] = [];
  for (const raw of messages.slice(-MAX_PERSISTED_MESSAGES)) {
    if (!raw || typeof raw !== "object") continue;
    const source = raw as Partial<ChatMessageType>;
    const text = truncateText(source.text, remainingChars);
    if (!text) continue;
    const message: ChatMessageType = {
      role: typeof source.role === "string" ? source.role : "assistant",
      text,
    };
    const aiContextContent = truncateText(source.aiContextContent, remainingChars);
    if (aiContextContent) message.aiContextContent = aiContextContent;
    if (typeof source.excludeFromAiContext === "boolean") message.excludeFromAiContext = source.excludeFromAiContext;
    const question = truncateText(source.question, remainingChars);
    if (question) message.question = question;
    if (source.queryRunId == null || typeof source.queryRunId === "string") message.queryRunId = source.queryRunId;
    if (typeof source.answerMode === "string") message.answerMode = source.answerMode;
    if (typeof source.answerSource === "string") message.answerSource = source.answerSource;
    if (typeof source.confidence === "number" && Number.isFinite(source.confidence)) message.confidence = source.confidence;
    if (Array.isArray(source.evidence)) message.evidence = source.evidence;
    if (Array.isArray(source.citedClaimIds)) message.citedClaimIds = source.citedClaimIds.filter((id) => typeof id === "string");
    if (Array.isArray(source.citedSentenceIds)) message.citedSentenceIds = source.citedSentenceIds.filter((id) => typeof id === "string");
    if (Array.isArray(source.citedSourceIds)) message.citedSourceIds = source.citedSourceIds.filter((id) => typeof id === "string");
    if (Array.isArray(source.sources)) message.sources = source.sources;
    const actionLabel = truncateText(source.actionLabel, remainingChars);
    if (actionLabel) message.actionLabel = actionLabel;
    if (typeof source.actionHref === "string" && source.actionHref.startsWith("/")) message.actionHref = source.actionHref;
    if (typeof source.progressPercent === "number" && Number.isFinite(source.progressPercent)) {
      message.progressPercent = Math.max(0, Math.min(100, source.progressPercent));
    }
    sanitized.push(message);
    if (remainingChars.value <= 0) break;
  }
  return sanitized;
}

function safeJsonParse(raw: string): Partial<PersistedChatSession> | null {
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Partial<PersistedChatSession>) : null;
  } catch {
    return null;
  }
}

function sanitizePersistedSession(payload: Partial<PersistedChatSession>): PersistedChatSession {
  return {
    messages: sanitizePersistedMessages(payload.messages),
    contextNotice: typeof payload.contextNotice === "string" || payload.contextNotice === null ? payload.contextNotice : null,
    draft: typeof payload.draft === "string" ? payload.draft.slice(0, MAX_PERSISTED_CHARS) : "",
    chatMode: payload.chatMode === "query" || payload.chatMode === "train" ? payload.chatMode : undefined,
    selectedChatKbUuid: typeof payload.selectedChatKbUuid === "string" ? payload.selectedChatKbUuid : undefined,
    selectedTrainKbUuid: typeof payload.selectedTrainKbUuid === "string" ? payload.selectedTrainKbUuid : undefined,
    activeTrainingRunId: typeof payload.activeTrainingRunId === "string" ? payload.activeTrainingRunId : undefined,
    activeTrainingTitle: typeof payload.activeTrainingTitle === "string" || payload.activeTrainingTitle === null ? payload.activeTrainingTitle : undefined,
    trainingVisualProgress:
      typeof payload.trainingVisualProgress === "number" && Number.isFinite(payload.trainingVisualProgress)
        ? Math.max(0, Math.min(99, Math.round(payload.trainingVisualProgress)))
        : undefined,
    trainingStartedAt: typeof payload.trainingStartedAt === "number" ? payload.trainingStartedAt : null,
    trainingEstimatedDurationMs: typeof payload.trainingEstimatedDurationMs === "number" ? payload.trainingEstimatedDurationMs : null,
  };
}

export function savePersistedChatSession(userId: number | string, payload: PersistedChatSession): void {
  const sanitized = sanitizePersistedSession(payload);
  localStorage.setItem(chatPersistKey(userId), JSON.stringify(sanitized));
}

export function loadPersistedChatSession(userId: number | string): PersistedChatSession | null {
  try {
    let raw = localStorage.getItem(chatPersistKey(userId));
    if (!raw) {
      const legacy = sessionStorage.getItem(chatLegacySessionKey(userId));
      if (legacy) {
        raw = legacy;
        localStorage.setItem(chatPersistKey(userId), legacy);
        sessionStorage.removeItem(chatLegacySessionKey(userId));
      }
    }
    if (!raw) return null;
    const data = safeJsonParse(raw);
    return data ? sanitizePersistedSession(data) : null;
  } catch {
    return null;
  }
}

export function clearLocalChatHistory(userId: number | string | null | undefined): void {
  try {
    clearChatContextNotice();
    if (userId != null) {
      localStorage.removeItem(chatPersistKey(userId));
      sessionStorage.removeItem(chatLegacySessionKey(userId));
    }
  } catch {
    // storage optional
  }
}

export function loadChatContextNoticeFallback(): string | null {
  try {
    return localStorage.getItem(CHAT_CONTEXT_STORAGE_KEY);
  } catch {
    return null;
  }
}
