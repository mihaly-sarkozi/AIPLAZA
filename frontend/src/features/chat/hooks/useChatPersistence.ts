import { useCallback, useEffect, useRef } from "react";

import { useAuthStore } from "../../../store/authStore";
import {
  loadChatContextNoticeFallback,
  loadPersistedChatSession,
  saveChatContextNotice,
  savePersistedChatSession,
} from "../services/chatPersistenceService";
import type { ChatMessageType, PersistedChatSession } from "../types";

type ChatPersistenceState = {
  userId: number | string | null | undefined;
  messages: ChatMessageType[];
  contextNotice: string | null;
  inputDraft: string;
  chatMode: "query" | "train";
  selectedChatKbUuid: string;
  selectedTrainKbUuid: string;
  conversationId: string;
  activeTrainingRunId: string | undefined;
  activeTrainingTitle: string | null;
  trainingVisualProgress: number;
  trainingStartedAtRef: React.MutableRefObject<number | null>;
  trainingEstimatedDurationMsRef: React.MutableRefObject<number | null>;
};

type ChatPersistenceRestorers = {
  setMessages: (messages: ChatMessageType[]) => void;
  setContextNotice: (contextNotice: string | null) => void;
  setInputDraft: (draft: string) => void;
  setChatMode: (mode: "query" | "train") => void;
  setSelectedChatKbUuid: (uuid: string) => void;
  setSelectedTrainKbUuid: (uuid: string) => void;
  setConversationId: (value: string) => void;
  setActiveTrainingRunId: (runId: string | undefined) => void;
  setActiveTrainingTitle: (title: string | null) => void;
  setTrainingVisualProgress: (progress: number) => void;
};

export function useChatPersistence(state: ChatPersistenceState, restorers: ChatPersistenceRestorers) {
  const persistEnabledRef = useRef(false);
  const lastUserIdRef = useRef<number | string | null>(null);
  const restorersRef = useRef(restorers);
  const messagesRef = useRef<ChatMessageType[]>(state.messages);
  const contextNoticeRef = useRef<string | null>(state.contextNotice);
  const inputDraftRef = useRef(state.inputDraft);
  const chatModeRef = useRef<"query" | "train">(state.chatMode);
  const selectedChatKbUuidRef = useRef(state.selectedChatKbUuid);
  const selectedTrainKbUuidRef = useRef(state.selectedTrainKbUuid);
  const conversationIdRef = useRef(state.conversationId);
  const activeTrainingRunIdRef = useRef<string | undefined>(state.activeTrainingRunId);
  const activeTrainingTitleRef = useRef<string | null>(state.activeTrainingTitle);
  const trainingVisualProgressRef = useRef(state.trainingVisualProgress);

  restorersRef.current = restorers;
  messagesRef.current = state.messages;
  contextNoticeRef.current = state.contextNotice;
  inputDraftRef.current = state.inputDraft;
  chatModeRef.current = state.chatMode;
  selectedChatKbUuidRef.current = state.selectedChatKbUuid;
  selectedTrainKbUuidRef.current = state.selectedTrainKbUuid;
  conversationIdRef.current = state.conversationId;
  activeTrainingRunIdRef.current = state.activeTrainingRunId;
  activeTrainingTitleRef.current = state.activeTrainingTitle;
  trainingVisualProgressRef.current = state.trainingVisualProgress;
  if (state.userId != null) lastUserIdRef.current = state.userId;

  const flushPersistToDisk = useCallback(() => {
    const id = useAuthStore.getState().user?.id ?? lastUserIdRef.current;
    if (id == null) return;
    const hasContent =
      messagesRef.current.length > 0 ||
      (inputDraftRef.current?.length ?? 0) > 0 ||
      contextNoticeRef.current != null;
    if (!persistEnabledRef.current && !hasContent) return;
    try {
      const payload: PersistedChatSession = {
        messages: messagesRef.current,
        contextNotice: contextNoticeRef.current,
        draft: inputDraftRef.current,
        chatMode: chatModeRef.current,
        selectedChatKbUuid: selectedChatKbUuidRef.current,
        selectedTrainKbUuid: selectedTrainKbUuidRef.current,
        conversationId: conversationIdRef.current,
        activeTrainingRunId: activeTrainingRunIdRef.current,
        activeTrainingTitle: activeTrainingTitleRef.current,
        trainingVisualProgress: trainingVisualProgressRef.current,
        trainingStartedAt: state.trainingStartedAtRef.current,
        trainingEstimatedDurationMs: state.trainingEstimatedDurationMsRef.current,
      };
      savePersistedChatSession(id, payload);
    } catch {
      // storage optional
    }
  }, [state.trainingEstimatedDurationMsRef, state.trainingStartedAtRef]);

  useEffect(() => {
    if (!state.userId) {
      persistEnabledRef.current = false;
      return;
    }
    persistEnabledRef.current = false;
    try {
      const data = loadPersistedChatSession(state.userId);
      if (data) {
        const restore = restorersRef.current;
        if (Array.isArray(data.messages)) restore.setMessages(data.messages);
        if ("contextNotice" in data && (data.contextNotice === null || typeof data.contextNotice === "string")) {
          restore.setContextNotice(data.contextNotice);
        } else {
          const saved = loadChatContextNoticeFallback();
          if (saved) restore.setContextNotice(saved);
        }
        if (typeof data.draft === "string") restore.setInputDraft(data.draft);
        if (data.chatMode === "query" || data.chatMode === "train") restore.setChatMode(data.chatMode);
        if (typeof data.selectedChatKbUuid === "string") restore.setSelectedChatKbUuid(data.selectedChatKbUuid);
        if (typeof data.selectedTrainKbUuid === "string") restore.setSelectedTrainKbUuid(data.selectedTrainKbUuid);
        if (typeof data.conversationId === "string") restore.setConversationId(data.conversationId);
        if (typeof data.activeTrainingRunId === "string" && data.activeTrainingRunId.trim()) {
          restore.setActiveTrainingRunId(data.activeTrainingRunId);
        }
        if (typeof data.activeTrainingTitle === "string") restore.setActiveTrainingTitle(data.activeTrainingTitle);
        if (typeof data.trainingVisualProgress === "number") {
          restore.setTrainingVisualProgress(Math.max(0, Math.min(99, Math.round(data.trainingVisualProgress))));
        }
        state.trainingStartedAtRef.current = typeof data.trainingStartedAt === "number" ? data.trainingStartedAt : null;
        state.trainingEstimatedDurationMsRef.current =
          typeof data.trainingEstimatedDurationMs === "number" ? data.trainingEstimatedDurationMs : null;
      } else {
        const saved = loadChatContextNoticeFallback();
        if (saved) restorersRef.current.setContextNotice(saved);
      }
    } catch {
      // storage optional
    } finally {
      persistEnabledRef.current = true;
    }
  }, [state.trainingEstimatedDurationMsRef, state.trainingStartedAtRef, state.userId]);

  useEffect(() => {
    if (!state.userId || !persistEnabledRef.current) return;
    flushPersistToDisk();
  }, [
    state.userId,
    state.messages,
    state.contextNotice,
    state.inputDraft,
    state.chatMode,
    state.selectedChatKbUuid,
    state.selectedTrainKbUuid,
    state.activeTrainingRunId,
    state.activeTrainingTitle,
    state.trainingVisualProgress,
    flushPersistToDisk,
  ]);

  useEffect(() => {
    const onHide = () => flushPersistToDisk();
    const onVis = () => {
      if (document.visibilityState === "hidden") onHide();
    };
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onVis);
      onHide();
    };
  }, [flushPersistToDisk]);

  useEffect(() => {
    saveChatContextNotice(state.contextNotice);
  }, [state.contextNotice]);

  return {
    flushPersistToDisk,
    messagesRef,
    contextNoticeRef,
  };
}
