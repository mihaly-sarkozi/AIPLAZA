import { useCallback, useEffect, useRef, type Dispatch, type RefObject, type SetStateAction, type MutableRefObject } from "react";
import { toast } from "sonner";

import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { sanitizeMessage } from "../../../utils/sanitize";
import { useCreateFileIngestMutation, useCreateTextIngestMutation, useIngestRun } from "../../knowledge-base/hooks/useKb";
import { estimateFileIngestRun } from "../../knowledge-base/services";
import { getTrainingFailureMessage, isTrainingActive } from "../../knowledge-base/utils/trainingProgress";
import type { ChatMessageType, FileCountingProgress, PendingFileTraining, PendingTextTraining } from "../types";
import { formatInteger, numberValue } from "../utils/chatNumbers";
import {
  estimateCountingDurationMs,
  estimatedTrainingProgress,
  estimateFileCharactersForProgress,
  estimateTrainingDurationMs,
  exactTrainingCharCount,
  isDuplicateOnlyTrainingRun,
} from "../utils/chatTraining";

const TRAINING_STALE_TIMEOUT_MS = 5 * 60 * 1000;

type UseChatTrainingFlowOptions = {
  effectiveTrainKbUuid: string;
  billingRestricted: boolean;
  billingOverview: { usage?: Record<string, unknown>; limits?: Record<string, unknown> } | null | undefined;
  inputDraft: string;
  pendingFileTraining: PendingFileTraining | null;
  pendingTextTraining: PendingTextTraining | null;
  fileEstimateLoading: boolean;
  activeTrainingRunId: string | undefined;
  activeTrainingTitle: string | null;
  locale: string;
  inputRef: RefObject<HTMLInputElement | null>;
  trainFileRef: RefObject<HTMLInputElement | null>;
  trainingStartedAtRef: MutableRefObject<number | null>;
  trainingEstimatedDurationMsRef: MutableRefObject<number | null>;
  setUser: (user: ReturnType<typeof useAuthStore.getState>["user"]) => void;
  appendMessage: (message: ChatMessageType) => void;
  setInputDraft: (value: string) => void;
  setFileEstimateLoading: (value: boolean) => void;
  setFileCountingProgress: Dispatch<SetStateAction<FileCountingProgress | null>>;
  setPendingFileTraining: (value: PendingFileTraining | null) => void;
  setPendingTextTraining: (value: PendingTextTraining | null) => void;
  setActiveTrainingRunId: (value: string | undefined) => void;
  setActiveTrainingTitle: (value: string | null) => void;
  setTrainingVisualProgress: Dispatch<SetStateAction<number>>;
  flushPersistToDisk: () => void;
  refreshBillingCounters: () => void;
  refreshKnowledgeBaseList: () => void;
  t: (key: string) => string;
};

export function useChatTrainingFlow({
  effectiveTrainKbUuid,
  billingRestricted,
  billingOverview,
  inputDraft,
  pendingFileTraining,
  pendingTextTraining,
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
  setInputDraft,
  setFileEstimateLoading,
  setFileCountingProgress,
  setPendingFileTraining,
  setPendingTextTraining,
  setActiveTrainingRunId,
  setActiveTrainingTitle,
  setTrainingVisualProgress,
  flushPersistToDisk,
  refreshBillingCounters,
  refreshKnowledgeBaseList,
  t,
}: UseChatTrainingFlowOptions) {
  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => (isTrainingActive(state.data?.status) ? 1500 : 4000),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const pendingTrainingConfirmation = pendingFileTraining !== null || pendingTextTraining !== null;
  const trainingOperationRunning =
    fileEstimateLoading ||
    createTextMutation.isPending ||
    createFileMutation.isPending ||
    isTrainingActive(activeTrainingRun?.status);

  const fileCountingTimerRef = useRef<number | null>(null);
  const trainingProgressTimerRef = useRef<number | null>(null);
  const staleTrainingTimeoutRef = useRef<number | null>(null);

  const stopFileCountingProgress = useCallback(() => {
    if (fileCountingTimerRef.current !== null) {
      window.clearInterval(fileCountingTimerRef.current);
      fileCountingTimerRef.current = null;
    }
  }, []);

  const startFileCountingProgress = useCallback(
    (file: File) => {
      stopFileCountingProgress();
      const estimatedCharacters = estimateFileCharactersForProgress(file);
      const durationMs = estimateCountingDurationMs(file);
      const startedAt = Date.now();
      setFileCountingProgress({ filename: file.name, percent: 3, estimatedCharacters });
      fileCountingTimerRef.current = window.setInterval(() => {
        const elapsed = Date.now() - startedAt;
        const ratio = Math.min(0.95, elapsed / durationMs);
        const eased = 1 - Math.pow(1 - ratio, 2);
        setFileCountingProgress((current) =>
          current ? { ...current, percent: Math.max(current.percent, Math.min(95, Math.round(eased * 95))) } : current
        );
      }, 180);
    },
    [setFileCountingProgress, stopFileCountingProgress]
  );

  const stopTrainingProgress = useCallback(() => {
    if (trainingProgressTimerRef.current !== null) {
      window.clearInterval(trainingProgressTimerRef.current);
      trainingProgressTimerRef.current = null;
    }
    trainingStartedAtRef.current = null;
    trainingEstimatedDurationMsRef.current = null;
  }, [trainingEstimatedDurationMsRef, trainingStartedAtRef]);

  const clearStaleTrainingTimeout = useCallback(() => {
    if (staleTrainingTimeoutRef.current !== null) {
      window.clearTimeout(staleTrainingTimeoutRef.current);
      staleTrainingTimeoutRef.current = null;
    }
  }, []);

  const startTrainingProgress = useCallback(
    (characterCount: number, startedAt = Date.now()) => {
      stopTrainingProgress();
      const durationMs = estimateTrainingDurationMs(characterCount);
      trainingStartedAtRef.current = startedAt;
      trainingEstimatedDurationMsRef.current = durationMs;
      setTrainingVisualProgress((current) => Math.max(current, estimatedTrainingProgress(Date.now() - startedAt, durationMs), 6));
      trainingProgressTimerRef.current = window.setInterval(() => {
        const effectiveStartedAt = trainingStartedAtRef.current ?? startedAt;
        const effectiveDurationMs = trainingEstimatedDurationMsRef.current ?? durationMs;
        const elapsed = Date.now() - effectiveStartedAt;
        const nextProgress = estimatedTrainingProgress(elapsed, effectiveDurationMs);
        setTrainingVisualProgress((current) => Math.max(current, Math.min(99, nextProgress)));
      }, 500);
    },
    [setTrainingVisualProgress, stopTrainingProgress, trainingEstimatedDurationMsRef, trainingStartedAtRef]
  );

  useEffect(
    () => () => {
      stopFileCountingProgress();
      stopTrainingProgress();
      clearStaleTrainingTimeout();
    },
    [clearStaleTrainingTimeout, stopFileCountingProgress, stopTrainingProgress]
  );

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingTitle || trainingProgressTimerRef.current !== null) return;
    const startedAt = trainingStartedAtRef.current;
    const durationMs = trainingEstimatedDurationMsRef.current;
    if (!startedAt || !durationMs) return;
    setTrainingVisualProgress((current) => Math.max(current, estimatedTrainingProgress(Date.now() - startedAt, durationMs), 6));
    trainingProgressTimerRef.current = window.setInterval(() => {
      const effectiveStartedAt = trainingStartedAtRef.current ?? startedAt;
      const effectiveDurationMs = trainingEstimatedDurationMsRef.current ?? durationMs;
      const nextProgress = estimatedTrainingProgress(Date.now() - effectiveStartedAt, effectiveDurationMs);
      setTrainingVisualProgress((current) => Math.max(current, Math.min(99, nextProgress)));
    }, 500);
  }, [activeTrainingRunId, activeTrainingTitle, setTrainingVisualProgress, trainingEstimatedDurationMsRef, trainingStartedAtRef]);

  useEffect(() => {
    clearStaleTrainingTimeout();
    if (!activeTrainingRunId || !activeTrainingRun || !isTrainingActive(activeTrainingRun.status)) return;
    const lastUpdatedRaw = activeTrainingRun.updated_at || activeTrainingRun.started_at || activeTrainingRun.created_at;
    const lastUpdatedAtMs = Date.parse(lastUpdatedRaw);
    const ageMs = Number.isFinite(lastUpdatedAtMs) ? Math.max(0, Date.now() - lastUpdatedAtMs) : 0;
    const waitMs = Math.max(10_000, TRAINING_STALE_TIMEOUT_MS - ageMs);
    staleTrainingTimeoutRef.current = window.setTimeout(() => {
      appendMessage({ role: "training-status", text: t("chat.trainingStaleWarning") });
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
    if (activeTrainingRun.status === "completed" || activeTrainingRun.status === "partial_success") {
      const u = useAuthStore.getState().user;
      if (u && u.tenant_kb_has_training !== true) setUser({ ...u, tenant_kb_has_training: true });
      if (isDuplicateOnlyTrainingRun(activeTrainingRun)) {
        appendMessage({ role: "training-status", text: t("chat.trainingAlreadyLoaded") });
      } else {
        const exactCharText = exactTrainingCharCount(activeTrainingRun);
        const exactCharMessage =
          exactCharText > 0 ? ` ${t("chat.fileCharacterCount").replace("{{count}}", formatInteger(exactCharText, locale))}` : "";
        appendMessage({
          role: "training-status",
          text: `Tanítás: ${
            activeTrainingRun.status === "partial_success" ? t("chat.trainingStatusPartialSuccess") : t("chat.trainingStatusCompleted")
          } 100%.${exactCharMessage}`,
        });
      }
      refreshKnowledgeBaseList();
    } else {
      appendMessage({ role: "assistant", text: getTrainingFailureMessage(activeTrainingRun, t) ?? t("chat.trainingFailed") });
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
    locale,
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
    appendMessage({ role: "assistant", text: getApiErrorMessage(activeTrainingRunQuery.error) ?? t("chat.trainingFailed") });
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
    appendMessage,
    inputRef,
    refreshBillingCounters,
    setActiveTrainingRunId,
    setActiveTrainingTitle,
    setTrainingVisualProgress,
    stopTrainingProgress,
    t,
  ]);

  const onSelectTrainingFile = async (file: File | null) => {
    if (!file || trainingOperationRunning || pendingTrainingConfirmation || billingRestricted) return;
    if (!effectiveTrainKbUuid) {
      toast.error(t("chat.selectTrainingKb"));
      return;
    }
    const title = file.name;
    appendMessage({ role: "user", text: title, excludeFromAiContext: true });
    setFileEstimateLoading(true);
    startFileCountingProgress(file);
    try {
      const estimate = await estimateFileIngestRun(effectiveTrainKbUuid, [file]);
      stopFileCountingProgress();
      setFileCountingProgress((current) => (current ? { ...current, percent: 100 } : current));
      const exactCharCount = Math.max(0, Math.round(Number(estimate.total_char_count ?? 0)));
      const charCountText = formatInteger(exactCharCount, locale);
      if (!estimate.can_start) {
        const reason = t("chat.fileTrainingQuotaBlocked");
        appendMessage({
          role: "training-status",
          text: `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingCannotStart")}: ${reason}`,
          actionLabel: t("chat.expandTrainingQuota"),
          actionHref: "/admin/csomagok",
        });
        toast.error(reason);
        appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
        if (trainFileRef.current) trainFileRef.current.value = "";
        return;
      }
      appendMessage({
        role: "training-status",
        text: `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingStartQuestion")}`,
      });
      setPendingFileTraining({ file, kbUuid: effectiveTrainKbUuid, title, characterCount: exactCharCount });
    } catch (error) {
      stopFileCountingProgress();
      const message = getApiErrorMessage(error) ?? t("chat.fileEstimateError");
      toast.error(message);
      appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
      if (trainFileRef.current) trainFileRef.current.value = "";
      return;
    } finally {
      setFileEstimateLoading(false);
      window.setTimeout(() => setFileCountingProgress(null), 350);
    }
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const startPendingFileTraining = () => {
    if (!pendingFileTraining) return;
    const pending = pendingFileTraining;
    setPendingFileTraining(null);
    setActiveTrainingTitle(pending.title);
    startTrainingProgress(pending.characterCount);
    createFileMutation.mutate(
      { kbUuid: pending.kbUuid, files: [pending.file], characterCounts: [pending.characterCount] },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          refreshBillingCounters();
          if (trainFileRef.current) trainFileRef.current.value = "";
        },
        onError: (error) => {
          setActiveTrainingTitle(null);
          stopTrainingProgress();
          setTrainingVisualProgress(0);
          toast.error(getApiErrorMessage(error) ?? t("chat.fileTrainingStartError"));
          appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
        },
      }
    );
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const cancelPendingFileTraining = () => {
    setPendingFileTraining(null);
    appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const startPendingTextTraining = () => {
    if (!pendingTextTraining) return;
    const pending = pendingTextTraining;
    setPendingTextTraining(null);
    setActiveTrainingTitle(t("chat.textTrainingLabel"));
    startTrainingProgress(pending.text.length);
    createTextMutation.mutate(
      { kbUuid: pending.kbUuid, title: pending.title, text: pending.text },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          refreshBillingCounters();
          setTimeout(() => inputRef.current?.focus(), 50);
        },
        onError: (error) => {
          setActiveTrainingTitle(null);
          stopTrainingProgress();
          setTrainingVisualProgress(0);
          toast.error(getApiErrorMessage(error) ?? t("chat.textTrainingStartError"));
          appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
        },
      }
    );
  };

  const cancelPendingTextTraining = () => {
    setPendingTextTraining(null);
    appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const onSubmitTextTraining = () => {
    const value = inputDraft.trim();
    if (!value || trainingOperationRunning || pendingTrainingConfirmation || billingRestricted) return;
    if (!effectiveTrainKbUuid) {
      toast.error(t("chat.selectTrainingKb"));
      return;
    }
    const title = sanitizeMessage(value);
    const charCount = value.length;
    const charCountText = formatInteger(charCount, locale);
    setInputDraft("");
    appendMessage({ role: "user", text: title, excludeFromAiContext: true });
    const training = ((billingOverview?.usage ?? {}).training as Record<string, unknown> | undefined) ?? {};
    const limits = billingOverview?.limits ?? {};
    const used = numberValue(training.trained_chars);
    const total = numberValue(training.available_training_chars ?? limits.training_chars_available);
    if (total > 0 && Math.max(0, total - used) < charCount) {
      const reason = t("chat.fileTrainingQuotaBlocked");
      appendMessage({
        role: "training-status",
        text: `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingCannotStart")}: ${reason}`,
        actionLabel: t("chat.expandTrainingQuota"),
        actionHref: "/admin/csomagok",
      });
      toast.error(reason);
      appendMessage({ role: "training-status", text: t("chat.trainingAborted") });
      setTimeout(() => inputRef.current?.focus(), 50);
      return;
    }
    appendMessage({
      role: "training-status",
      text: `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingStartQuestion")}`,
    });
    setPendingTextTraining({ kbUuid: effectiveTrainKbUuid, title: t("chat.textTrainingTitle"), text: value });
  };

  return {
    activeTrainingRun,
    pendingTrainingConfirmation,
    trainingOperationRunning,
    onSelectTrainingFile,
    startPendingFileTraining,
    cancelPendingFileTraining,
    startPendingTextTraining,
    cancelPendingTextTraining,
    onSubmitTextTraining,
  };
}
