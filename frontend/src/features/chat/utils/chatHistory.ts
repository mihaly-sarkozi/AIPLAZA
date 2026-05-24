import type { ChatMessageType } from "../types";

export const MAX_CHAT_MESSAGES = 100;
export const MAX_CONVERSATION_CONTEXT_MESSAGES = 10;
export const MAX_RETRIEVAL_HISTORY_ITEMS = 4;
export const MAX_RETRIEVAL_HISTORY_CHARS = 320;

export function trimToLastN(messages: ChatMessageType[], n: number): ChatMessageType[] {
  if (messages.length <= n) return messages;
  return messages.slice(-n);
}

export function buildConversationHistory(messages: ChatMessageType[]): Array<{ role: "user" | "assistant"; content: string }> {
  const sanitized = messages.filter((message, index) => {
    if (!(message.role === "user" || message.role === "assistant")) return false;
    const candidate = String(message.aiContextContent || message.text || "").trim();
    if (!candidate) return false;
    if (message.excludeFromAiContext) return false;
    if (message.role !== "user") return true;
    // Training flow user input maradjon a UI-ban, de ne menjen az LLM kontextusába.
    for (let i = index + 1; i < messages.length; i += 1) {
      const nextRole = messages[i]?.role;
      if (nextRole === "training-status") return false;
      if (nextRole === "assistant" || nextRole === "user") return true;
    }
    return true;
  });
  return sanitized.slice(-MAX_CONVERSATION_CONTEXT_MESSAGES).map((message) => ({
    role: message.role === "user" ? "user" : "assistant",
    content: String(message.aiContextContent || message.text || "").trim(),
  }));
}

export function buildRetrievalHistory(messages: ChatMessageType[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const message of [...messages].reverse()) {
    if (message.role !== "assistant") continue;
    const blocks = Array.isArray(message.contextBlocks) ? message.contextBlocks : [];
    for (const block of blocks) {
      const raw = String((block?.snippet as string) || (block?.text as string) || "").trim();
      if (!raw) continue;
      const text = raw.length > MAX_RETRIEVAL_HISTORY_CHARS ? `${raw.slice(0, MAX_RETRIEVAL_HISTORY_CHARS)}...` : raw;
      const key = text.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(text);
      if (out.length >= MAX_RETRIEVAL_HISTORY_ITEMS) return out;
    }
  }
  return out;
}

export function isClearHistoryCommand(value: string): boolean {
  const normalized = value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return normalized === "elozmeny torlese" || normalized === "torold az elozmenyt" || normalized === "elozmenyek torlese";
}
