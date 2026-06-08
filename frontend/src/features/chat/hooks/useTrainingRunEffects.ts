import { useCallback, useEffect, useRef, type RefObject } from "react";

import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import type { useIngestRun } from "../../knowledge-base/hooks/useKb";
import { getTrainingFailureMessage, isTrainingActive } from "../../knowledge-base/utils/trainingProgress";
import type { ChatMessageType } from "../types";
import { estimatedTrainingProgress, isDuplicateOnlyTrainingRun } from "../utils/chatTraining";

const TRAINING_STALE_TIMEOUT_MS = 5 * 60 * 1000;

type UseTrainingRunEffectsOptions = {
  activeTrainingRun: ReturnType<typeof useIngestRun>["data"];
  activeTrainingRunQuery: { isError: boolean; error: unknown };
  activeTrainingRunId: string | undefined;
  activeTrainingTitle: string | null;
  inputRef: RefObject<HTMLInputElement | null>;
  trainingStartedAtRef: React.MutableRefObject<number | null>;
  trainingEstimatedDurationMsRef: React.MutableRefObject<number | null>;
  setUser: (user: ReturnType<typeof useAuthStore.getState>["user"]) => void;
  appendMessage: (message: ChatMessageType) => void;
  patchTextTrainingUserMessage: (patch: {
    textTrainingOutcome: "success" | "error" | "cancelled";
    textTrainingOutcomeDetail?: string;
    trainingRun?: ReturnType<typeof useIngestRun>["data"];
  }) => void;
  setActiveTrainingRunId: (value: string | undefined) => void;
  setActiveTrainingTitle: (value: string | null) => void;
  setTrainingVisualProgress: React.Dispatch<React.SetStateAction<number>>;
  flushPersistToDisk: () => void;
  refreshBillingCounters: () => void;
  refreshKnowledgeBaseList: () => void;
  stopTrainingProgress: () => void;
  t: (key: string) => string;
};

export function useTrainingRunEffects({
  activeTrainingRun,
  activeTrainingRunQuery,
  activeTrainingRunId,
  activeTrainingTitle,
  inputRef,
  trainingStartedAtRef,
  trainingEstimatedDurationMsRef,
  setUser,
  appendMessage,
  patchTextTrainingUserMessage,
  setActiveTrainingRunId,
  setActiveTrainingTitle,
  setTrainingVisualProgress,
  flushPersistToDisk,
  refreshBillingCounters,
  refreshKnowledgeBaseList,
  stopTrainingProgress,
  t,
}: UseTrainingRunEffectsOptions) {
  const staleTrainingTimeoutRef = useRef<number | null>(null);
  const handledTrainingRunIdRef = useRef<string | null>(null);
  const handledTrainingErrorRunIdRef = useRef<string | null>(null);

  const clearStaleTrainingTimeout = useCallback(() => {
    if (staleTrainingTimeoutRef.current !== null) {
      window.clearTimeout(staleTrainingTimeoutRef.current);
      staleTrainingTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => () => clearStaleTrainingTimeout(), [clearStaleTrainingTimeout]);

  useEffect(() => {
    handledTrainingRunIdRef.current = null;
    handledTrainingErrorRunIdRef.current = null;
  }, [activeTrainingRunId]);

  useEffect(() => {
    clearStaleTrainingTimeout();
    if (!activeTrainingRunId || !activeTrainingRun || !isTrainingActive(activeTrainingRun.status)) return;
    const lastUpdatedRaw = activeTrainingRun.updated_at || activeTrainingRun.started_at || activeTrainingRun.created_at;
    const lastUpdatedAtMs = Date.parse(lastUpdatedRaw);
    const ageMs = Number.isFinite(lastUpdatedAtMs) ? Math.max(0, Date.now() - lastUpdatedAtMs) : 0;
    const waitMs = Math.max(10_000, TRAINING_STALE_TIMEOUT_MS - ageMs);
    staleTrainingTimeoutRef.current = window.setTimeout(() => {
      patchTextTrainingUserMessage({
        textTrainingOutcome: "error",
        textTrainingOutcomeDetail: t("chat.trainingStaleWarning"),
      });
      setActiveTrainingRunId(undefined);
      setActiveTrainingTitle(null);
      stopTrainingProgress();
      setTrainingVisualProgress(0);
      refreshBillingCounters();
      refreshKnowledgeBaseList();
      requestAnimationFrame(() => flushPersistToDisk());
    }, waitMs);
    return () => clearStaleTrainingTimeout();
  }, [
    activeTrainingRun,
    activeTrainingRunId,
    appendMessage,
    clearStaleTrainingTimeout,
    flushPersistToDisk,
    patchTextTrainingUserMessage,
    refreshBillingCounters,
    refreshKnowledgeBaseList,
    setActiveTrainingRunId,
    setActiveTrainingTitle,
    setTrainingVisualProgress,
    stopTrainingProgress,
    t,
  ]);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRun || isTrainingActive(activeTrainingRun.status)) return;
    if (handledTrainingRunIdRef.current === activeTrainingRunId) return;
    handledTrainingRunIdRef.current = activeTrainingRunId;
    if (activeTrainingRun.status === "completed" || activeTrainingRun.status === "partial_success") {
      const user = useAuthStore.getState().user;
      if (user && user.tenant_kb_has_training !== true) setUser({ ...user, tenant_kb_has_training: true });
      if (isDuplicateOnlyTrainingRun(activeTrainingRun)) {
        patchTextTrainingUserMessage({
          textTrainingOutcome: "error",
          textTrainingOutcomeDetail: t("chat.trainingAlreadyLoaded"),
        });
      } else {
        patchTextTrainingUserMessage({
          textTrainingOutcome: "success",
          trainingRun: activeTrainingRun,
        });
      }
      refreshKnowledgeBaseList();
    } else {
      const failureMessage = getTrainingFailureMessage(activeTrainingRun, t) ?? t("chat.trainingFailed");
      patchTextTrainingUserMessage({ textTrainingOutcome: "error", textTrainingOutcomeDetail: failureMessage });
    }
    setActiveTrainingRunId(undefined);
    setActiveTrainingTitle(null);
    stopTrainingProgress();
    setTrainingVisualProgress(0);
    refreshBillingCounters();
    setTimeout(() => inputRef.current?.focus(), 50);
    requestAnimationFrame(() => flushPersistToDisk());
  }, [
    activeTrainingRun,
    activeTrainingRunId,
    appendMessage,
    flushPersistToDisk,
    inputRef,
    patchTextTrainingUserMessage,
    refreshBillingCounters,
    refreshKnowledgeBaseList,
    setActiveTrainingRunId,
    setActiveTrainingTitle,
    setTrainingVisualProgress,
    setUser,
    stopTrainingProgress,
    t,
  ]);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRunQuery.isError) return;
    if (handledTrainingErrorRunIdRef.current === activeTrainingRunId) return;
    handledTrainingErrorRunIdRef.current = activeTrainingRunId;
    const pollError = getApiErrorMessage(activeTrainingRunQuery.error) ?? t("chat.trainingFailed");
    patchTextTrainingUserMessage({ textTrainingOutcome: "error", textTrainingOutcomeDetail: pollError });
    setActiveTrainingRunId(undefined);
    setActiveTrainingTitle(null);
    stopTrainingProgress();
    setTrainingVisualProgress(0);
    refreshBillingCounters();
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [
    activeTrainingRunId,
    activeTrainingRunQuery.error,
    activeTrainingRunQuery.isError,
    activeTrainingRun,
    appendMessage,
    inputRef,
    patchTextTrainingUserMessage,
    refreshBillingCounters,
    setActiveTrainingRunId,
    setActiveTrainingTitle,
    setTrainingVisualProgress,
    stopTrainingProgress,
    t,
  ]);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingTitle) return;
    const startedAt = trainingStartedAtRef.current;
    const durationMs = trainingEstimatedDurationMsRef.current;
    if (!startedAt || !durationMs) return;
    setTrainingVisualProgress((current) => Math.max(current, estimatedTrainingProgress(Date.now() - startedAt, durationMs), 6));
  }, [activeTrainingRunId, activeTrainingTitle, setTrainingVisualProgress, trainingEstimatedDurationMsRef, trainingStartedAtRef]);
}
