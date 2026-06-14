import { useState, useRef, useCallback, useMemo } from "react";
import { toast } from "sonner";
import ChatBillingRestrictionPanel from "../components/ChatBillingRestrictionPanel";
import ChatComposer from "../components/ChatComposer";
import ChatMessagesList from "../components/ChatMessagesList";
import TrainingConfirmationModal from "../components/TrainingConfirmationModal";
import { useAuthStore } from "../../../store/authStore";
import { useKbList } from "../../knowledge-base/hooks/useKb";
import { getTrainingProgress } from "../../knowledge-base/utils/trainingProgress";
import { useTranslation } from "../../../i18n";
import { useBillingAccessStatus, useBillingOverview } from "../../billing/hooks/useBilling";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../../queryKeys";
import type {
  ChatMessageType,
  FileCountingProgress,
  PendingFileTraining,
} from "../types";
import { MAX_CHAT_MESSAGES, trimToLastN } from "../utils/chatHistory";
import { downloadTxt, serializeProcessToTxt } from "../utils/chatExport";
import { buildTrainingSuccessDetail, combineTrainingProgress, resolveTrainingCharCount } from "../utils/chatTraining";
import {
  findLastPendingTextTrainingMessage,
  patchLastPendingTextTrainingCharacterCount,
  patchLastPendingTextTrainingMessage,
} from "../utils/textTrainingMessage";
import type { IngestRun } from "../../knowledge-base/services";
import { clearLocalChatHistory } from "../services/chatPersistenceService";
import { useChatPersistence } from "../hooks/useChatPersistence";
import { useChatScroll } from "../hooks/useChatScroll";
import { useChatSendMessage } from "../hooks/useChatSendMessage";
import { useChatSession } from "../hooks/useChatSession";
import { useChatTrainingFlow } from "../hooks/useChatTrainingFlow";

/** Üres tömb = Mind (minden tudástár); nem üres = csak a kiválasztott uuid-k. */

export default function ChatPage() {
  const { t, locale } = useTranslation();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);
  const { data: settings } = useLocaleSettings();
  const kbListQuery = useKbList();
  const kbList = useMemo(() => kbListQuery.data ?? [], [kbListQuery.data]);
  const { data: billingOverview } = useBillingOverview();
  const { data: billingAccessStatus } = useBillingAccessStatus({ refetchOnWindowFocus: false });
  const billingRestricted =
    billingAccessStatus?.restricted === true || billingAccessStatus?.payment_warning?.is_expired === true;
  const subscription = billingOverview?.subscription ?? {};
  const trialEndsAt = typeof subscription.trial_ends_at === "string" ? subscription.trial_ends_at : null;
  const freeTrialExpired =
    billingRestricted &&
    String(subscription.plan_code ?? "").toLowerCase() === "free" &&
    (String(subscription.status ?? "").toLowerCase() === "restricted" ||
      (trialEndsAt != null && new Date(trialEndsAt).getTime() <= Date.now()));
  const canManageBilling = user?.role === "owner";
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [chatMode, setChatMode] = useState<"query" | "train">("query");
  const [selectedChatKbUuid, setSelectedChatKbUuid] = useState("");
  const [selectedTrainKbUuid, setSelectedTrainKbUuid] = useState("");
  const [dragOverTrainFile, setDragOverTrainFile] = useState(false);
  const [contextNotice, setContextNotice] = useState<string | null>(null);
  const [inputDraft, setInputDraft] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [fileEstimateLoading, setFileEstimateLoading] = useState(false);
  const [fileCountingProgress, setFileCountingProgress] = useState<FileCountingProgress | null>(null);
  const [pendingFileTraining, setPendingFileTraining] = useState<PendingFileTraining | null>(null);
  const [activeTrainingRunId, setActiveTrainingRunId] = useState<string | undefined>(undefined);
  const [activeTrainingTitle, setActiveTrainingTitle] = useState<string | null>(null);
  const [trainingVisualProgress, setTrainingVisualProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const trainFileRef = useRef<HTMLInputElement | null>(null);
  const messagesRef = useRef<ChatMessageType[]>(messages);
  const contextNoticeRef = useRef<string | null>(contextNotice);
  const trainingStartedAtRef = useRef<number | null>(null);
  const trainingEstimatedDurationMsRef = useRef<number | null>(null);
  const { messageScrollRef, messagesEndRef } = useChatScroll(messages);
  const chatPersistence = useChatPersistence(
    {
      userId: user?.id,
      messages,
      contextNotice,
      inputDraft,
      chatMode,
      selectedChatKbUuid,
      selectedTrainKbUuid,
      conversationId,
      activeTrainingRunId,
      activeTrainingTitle,
      trainingVisualProgress,
      trainingStartedAtRef,
      trainingEstimatedDurationMsRef,
    },
    {
      setMessages,
      setContextNotice,
      setInputDraft,
      setChatMode,
      setSelectedChatKbUuid,
      setSelectedTrainKbUuid,
      setConversationId,
      setActiveTrainingRunId,
      setActiveTrainingTitle,
      setTrainingVisualProgress,
    }
  );
  messagesRef.current = chatPersistence.messagesRef.current;
  contextNoticeRef.current = chatPersistence.contextNoticeRef.current;
  const flushPersistToDisk = chatPersistence.flushPersistToDisk;

  const {
    trainableKbList,
    selectableChatKbList,
    effectiveTrainKbUuid,
    effectiveChatKbUuid,
    selectedTopKbUuid,
    selectedTopKbLabel,
    composerUsage,
  } = useChatSession({
    kbList,
    kbListFetched: kbListQuery.isFetched,
    billingOverview,
    chatMode,
    selectedChatKbUuid,
    selectedTrainKbUuid,
    setChatMode,
    setSelectedChatKbUuid,
    setSelectedTrainKbUuid,
    locale,
    t,
  });
  const noAccessibleKnowledgeBase = kbListQuery.isFetched && selectableChatKbList.length === 0;
  const chatEmptyStateKey = noAccessibleKnowledgeBase
    ? "chat.noAccessibleKnowledgeBase"
    : trainableKbList.length === 0
      ? "chat.emptyStateQueryOnly"
      : "chat.emptyState";

  const appendMessage = useCallback((msg: ChatMessageType) => {
    setMessages((prev) => {
      const next = trimToLastN([...prev, msg], MAX_CHAT_MESSAGES);
      return next;
    });
  }, []);
  const patchTextTrainingCharacterCount = useCallback((characterCount: number) => {
    setMessages((prev) =>
      trimToLastN(patchLastPendingTextTrainingCharacterCount(prev, characterCount), MAX_CHAT_MESSAGES)
    );
  }, []);
  const patchTextTrainingUserMessage = useCallback(
    (patch: {
      textTrainingOutcome: "success" | "error" | "cancelled";
      textTrainingOutcomeDetail?: string;
      trainingRun?: IngestRun | null;
    }) => {
      setMessages((prev) => {
        const pending = findLastPendingTextTrainingMessage(prev);
        const detail =
          patch.textTrainingOutcome === "success"
            ? buildTrainingSuccessDetail(
                resolveTrainingCharCount(patch.trainingRun, pending?.textTrainingCharacterCount),
                locale,
                t
              )
            : (patch.textTrainingOutcomeDetail ?? t("chat.trainingFailed"));
        return trimToLastN(
          patchLastPendingTextTrainingMessage(prev, {
            textTrainingOutcome: patch.textTrainingOutcome,
            textTrainingOutcomeDetail: detail,
          }),
          MAX_CHAT_MESSAGES
        );
      });
    },
    [locale, t]
  );
  const refreshBillingCounters = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
  }, [queryClient]);
  const refreshKnowledgeBaseList = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.kb });
  }, [queryClient]);

  const trainingFlow = useChatTrainingFlow({
    effectiveTrainKbUuid,
    billingRestricted,
    billingOverview,
    inputDraft,
    pendingFileTraining,
    fileEstimateLoading,
    activeTrainingRunId,
    activeTrainingTitle,
    locale,
    inputRef,
    trainFileRef,
    trainingStartedAtRef,
    trainingEstimatedDurationMsRef,
    setUser,
    appendMessage,
    patchTextTrainingUserMessage,
    patchTextTrainingCharacterCount,
    setInputDraft,
    setFileEstimateLoading,
    setFileCountingProgress,
    setPendingFileTraining,
    setActiveTrainingRunId,
    setActiveTrainingTitle,
    setTrainingVisualProgress,
    flushPersistToDisk,
    refreshBillingCounters,
    refreshKnowledgeBaseList,
    t,
  });
  const trainingProgress = useMemo(() => getTrainingProgress(trainingFlow.activeTrainingRun), [trainingFlow.activeTrainingRun]);
  const displayedTrainingProgress = combineTrainingProgress(trainingProgress, trainingVisualProgress);
  const {
    pendingTrainingConfirmation,
    trainingOperationRunning,
    onSelectTrainingFile,
    startPendingFileTraining,
    cancelPendingFileTraining,
    onSubmitTextTraining,
  } = trainingFlow;

  const clearHistory = useCallback(() => {
    setMessages([]);
    setContextNotice(null);
    setInputDraft("");
    setConversationId("");
    setPendingFileTraining(null);
    clearLocalChatHistory(useAuthStore.getState().user?.id);
  }, []);

  const exportChatProcess = useCallback(() => {
    const content = serializeProcessToTxt({
      locale,
      mode: chatMode,
      selectedKbLabel: selectedTopKbLabel,
      messages: messagesRef.current,
      contextNotice: contextNoticeRef.current,
      timezone: settings?.timezone,
      dateFormat: settings?.date_format,
      timeFormat: settings?.time_format,
    });
    const stamp = new Date().toISOString().replace(/[:]/g, "-").replace(/\..+$/, "");
    downloadTxt(`aiplaza-chat-folyamat-${stamp}.txt`, `${content}\n`);
    toast.success("A folyamat exportálva lett .txt fájlba.");
  }, [locale, chatMode, selectedTopKbLabel, settings?.timezone, settings?.date_format, settings?.time_format]);

  const send = useChatSendMessage({
    inputDraft,
    loading,
    billingRestricted,
    effectiveChatKbUuid,
    conversationId,
    setConversationId,
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
  });

  if (billingRestricted) {
    return <ChatBillingRestrictionPanel freeTrialExpired={freeTrialExpired} canManageBilling={canManageBilling} t={t} />;
  }

  return (
    <div
      className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[var(--color-background)] text-[var(--color-foreground)]"
      onDragOver={(event) => {
        if (chatMode !== "train") return;
        event.preventDefault();
        setDragOverTrainFile(true);
      }}
      onDragLeave={(event) => {
        if (chatMode !== "train") return;
        const nextTarget = event.relatedTarget as Node | null;
        if (nextTarget && event.currentTarget.contains(nextTarget)) return;
        setDragOverTrainFile(false);
      }}
      onDrop={(event) => {
        if (chatMode !== "train") return;
        event.preventDefault();
        setDragOverTrainFile(false);
        onSelectTrainingFile(event.dataTransfer?.files?.[0] ?? null);
      }}
    >
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <div className="min-w-0 flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-hidden px-4 pt-2 pb-2">
            <div
              ref={messageScrollRef}
              className="relative h-full min-h-0 overflow-y-auto px-2 pt-2 pb-2"
            >
              <ChatMessagesList
                contextNotice={contextNotice}
                messages={messages}
                loading={loading}
                fileCountingProgress={fileCountingProgress}
                activeTrainingTitle={activeTrainingTitle}
                displayedTrainingProgress={displayedTrainingProgress}
                messagesEndRef={messagesEndRef}
                emptyStateKey={chatEmptyStateKey}
                t={t}
              />
            </div>
          </div>

          {noAccessibleKnowledgeBase ? (
            <div className="shrink-0 h-6" />
          ) : (
            <ChatComposer
              chatMode={chatMode}
              setChatMode={setChatMode}
              dragOverTrainFile={dragOverTrainFile}
              setDragOverTrainFile={setDragOverTrainFile}
              inputDraft={inputDraft}
              setInputDraft={setInputDraft}
              loading={loading}
              messagesLength={messages.length}
              contextNotice={contextNotice}
              trainingOperationRunning={trainingOperationRunning}
              pendingTrainingConfirmation={pendingTrainingConfirmation}
              selectedTopKbUuid={selectedTopKbUuid}
              selectedTopKbLabel={selectedTopKbLabel}
              selectableChatKbList={selectableChatKbList}
              trainableKbList={trainableKbList}
              composerUsage={composerUsage}
              inputRef={inputRef}
              trainFileRef={trainFileRef}
              onSelectTrainingFile={onSelectTrainingFile}
              clearHistory={clearHistory}
              exportChatProcess={exportChatProcess}
              send={send}
              onSubmitTextTraining={onSubmitTextTraining}
              setSelectedTrainKbUuid={setSelectedTrainKbUuid}
              setSelectedChatKbUuid={setSelectedChatKbUuid}
              t={t}
            />
          )}
        </div>
      </div>

      <TrainingConfirmationModal
        open={pendingFileTraining !== null}
        filename={pendingFileTraining?.title ?? ""}
        characterCount={pendingFileTraining?.characterCount ?? 0}
        locale={locale}
        onCancel={cancelPendingFileTraining}
        onConfirm={startPendingFileTraining}
        t={t}
      />
    </div>
  );
}
