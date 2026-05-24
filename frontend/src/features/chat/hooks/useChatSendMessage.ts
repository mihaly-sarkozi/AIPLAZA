import { useCallback, type RefObject } from "react";

import api from "../../../api/axiosClient";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { sanitizeMessage } from "../../../utils/sanitize";
import { buildConversationHistory, buildRetrievalHistory, isClearHistoryCommand, MAX_CHAT_MESSAGES, trimToLastN } from "../utils/chatHistory";
import { dedupeChatSources, getEncodedHistoryText, shouldShowAnswerSources } from "../utils/chatSources";
import type { ChatApiRequest, ChatApiResponse, ChatMessageType } from "../types";

type UseChatSendMessageOptions = {
  inputDraft: string;
  loading: boolean;
  billingRestricted: boolean;
  effectiveChatKbUuid: string;
  messagesRef: RefObject<ChatMessageType[]>;
  inputRef: RefObject<HTMLInputElement | null>;
  appendMessage: (message: ChatMessageType) => void;
  clearHistory: () => void;
  setInputDraft: (value: string) => void;
  setLoading: (value: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessageType[]>>;
  flushPersistToDisk: () => void;
  refreshBillingCounters: () => void;
  t: (key: string) => string;
};

export function useChatSendMessage({
  inputDraft,
  loading,
  billingRestricted,
  effectiveChatKbUuid,
  messagesRef,
  inputRef,
  appendMessage,
  clearHistory,
  setInputDraft,
  setLoading,
  setMessages,
  flushPersistToDisk,
  refreshBillingCounters,
  t,
}: UseChatSendMessageOptions) {
  return useCallback(async () => {
    const raw = inputDraft.trim();
    if (!raw || loading || billingRestricted) return;

    const question = sanitizeMessage(raw);
    setInputDraft("");

    if (isClearHistoryCommand(question)) {
      clearHistory();
      appendMessage({ role: "assistant", text: t("chat.historyCleared") });
      requestAnimationFrame(() => flushPersistToDisk());
      return;
    }

    const conversationHistory = buildConversationHistory(messagesRef.current);
    const retrievalHistory = buildRetrievalHistory(messagesRef.current);
    appendMessage({ role: "user", text: question, aiContextContent: question });
    setTimeout(() => inputRef.current?.focus(), 50);
    setLoading(true);
    try {
      const payload: ChatApiRequest = {
        question,
        debug: true,
        conversation_history: conversationHistory,
        retrieval_history: retrievalHistory,
      };
      if (effectiveChatKbUuid) payload.kb_uuid = effectiveChatKbUuid;
      const res = await api.post<ChatApiResponse>("/chat", payload);
      const data = res.data;
      const answer = String(data?.answer || "").trim() || t("chat.insufficientInfo");
      const responseSources = Array.isArray(data?.sources) ? data.sources : [];
      const sources = shouldShowAnswerSources(data, answer, t("chat.insufficientInfo"), responseSources.length)
        ? dedupeChatSources(responseSources)
        : [];
      const encodedQuestionForHistory = getEncodedHistoryText(data, "encoded_latest_question", question);
      const encodedAnswerForHistory = getEncodedHistoryText(data, "encoded_answer_text", answer);
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i]?.role === "user" && String(next[i]?.text || "").trim() === question.trim()) {
            next[i] = { ...next[i], aiContextContent: encodedQuestionForHistory || question };
            break;
          }
        }
        return trimToLastN(next, MAX_CHAT_MESSAGES);
      });
      appendMessage({
        role: "assistant",
        text: answer,
        aiContextContent: encodedAnswerForHistory || answer,
        question,
        queryRunId: data?.query_run_id ?? null,
        answerMode: data?.answer_mode,
        answerSource: data?.answer_source,
        confidence: typeof data?.confidence === "number" ? data.confidence : undefined,
        evidence: Array.isArray(data?.evidence) ? data.evidence : [],
        citedClaimIds: Array.isArray(data?.cited_claim_ids) ? data.cited_claim_ids : [],
        citedSentenceIds: Array.isArray(data?.cited_sentence_ids) ? data.cited_sentence_ids : [],
        citedSourceIds: Array.isArray(data?.cited_source_ids) ? data.cited_source_ids : [],
        queryProfile: data?.query_profile,
        matchedChunks: Array.isArray(data?.matched_chunks) ? data.matched_chunks : [],
        claims: Array.isArray(data?.claims) ? data.claims : [],
        contextBlocks: Array.isArray(data?.context_blocks) ? data.context_blocks : [],
        sources,
        promptContext: data?.prompt_context && typeof data.prompt_context === "object" ? data.prompt_context : undefined,
        debug: data?.debug ?? null,
        encodedPromptContext: String(data?.encoded_prompt_context || ""),
        restoredPiiSpans: Array.isArray(data?.restored_pii_spans) ? data.restored_pii_spans : [],
      });
      refreshBillingCounters();
    } catch (err) {
      appendMessage({
        role: "assistant",
        text: getApiErrorMessage(err) ?? t("chat.serviceError"),
      });
    } finally {
      setLoading(false);
      requestAnimationFrame(() => {
        flushPersistToDisk();
        inputRef.current?.focus();
      });
    }
  }, [
    appendMessage,
    billingRestricted,
    clearHistory,
    effectiveChatKbUuid,
    flushPersistToDisk,
    inputDraft,
    inputRef,
    loading,
    messagesRef,
    refreshBillingCounters,
    setInputDraft,
    setLoading,
    setMessages,
    t,
  ]);
}
