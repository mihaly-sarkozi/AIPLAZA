import { useEffect, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";
import { toast } from "sonner";

import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage, isDuplicateContentError } from "../../../utils/getApiErrorMessage";
import { sanitizeMessage } from "../../../utils/sanitize";
import { useCreateFileIngestMutation, useCreateTextIngestMutation, useIngestRun } from "../../knowledge-base/hooks/useKb";
import { estimateFileIngestRun } from "../../knowledge-base/services";
import { getTrainingRunRefetchInterval, isTrainingActive } from "../../knowledge-base/utils/trainingProgress";
import type { IngestRun } from "../../knowledge-base/services";
import type { ChatMessageType, FileCountingProgress, PendingFileTraining } from "../types";
import { formatInteger, numberValue } from "../utils/chatNumbers";
import { useTrainingProgressTimers } from "./useTrainingProgressTimers";
import { useTrainingRunEffects } from "./useTrainingRunEffects";

type UseChatTrainingFlowOptions = {
  effectiveTrainKbUuid: string;
  billingRestricted: boolean;
  billingOverview: { usage?: Record<string, unknown>; limits?: Record<string, unknown> } | null | undefined;
  inputDraft: string;
  pendingFileTraining: PendingFileTraining | null;
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
  patchTextTrainingUserMessage: (patch: {
    textTrainingOutcome: "success" | "error" | "cancelled";
    textTrainingOutcomeDetail?: string;
    trainingRun?: IngestRun | null;
  }) => void;
  patchTextTrainingCharacterCount: (characterCount: number) => void;
  setInputDraft: (value: string) => void;
  setFileEstimateLoading: (value: boolean) => void;
  setFileCountingProgress: Dispatch<SetStateAction<FileCountingProgress | null>>;
  setPendingFileTraining: (value: PendingFileTraining | null) => void;
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
}: UseChatTrainingFlowOptions) {
  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => getTrainingRunRefetchInterval(state.data?.status),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const pendingTrainingConfirmation = pendingFileTraining !== null;
  const trainingOperationRunning =
    fileEstimateLoading ||
    createTextMutation.isPending ||
    createFileMutation.isPending ||
    isTrainingActive(activeTrainingRun?.status);

  const { startFileCountingProgress, stopFileCountingProgress, startTrainingProgress, stopTrainingProgress, resumeTrainingProgress } =
    useTrainingProgressTimers({
      trainingStartedAtRef,
      trainingEstimatedDurationMsRef,
      setFileCountingProgress,
      setTrainingVisualProgress,
    });

  useTrainingRunEffects({
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
  });

  useEffect(() => {
    resumeTrainingProgress(activeTrainingRunId, activeTrainingTitle);
  }, [activeTrainingRunId, activeTrainingTitle, resumeTrainingProgress]);

  const onSelectTrainingFile = async (file: File | null) => {
    if (!file || trainingOperationRunning || pendingTrainingConfirmation || billingRestricted) return;
    if (!effectiveTrainKbUuid) {
      toast.error(t("chat.selectTrainingKb"));
      return;
    }
    const title = file.name;
    appendMessage({ role: "user", text: title, excludeFromAiContext: true, textTrainingPending: true });
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
        patchTextTrainingUserMessage({
          textTrainingOutcome: "error",
          textTrainingOutcomeDetail: `${t("chat.trainingCannotStart")}: ${reason}`,
        });
        appendMessage({
          role: "training-status",
          text: `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingCannotStart")}: ${reason}`,
          actionLabel: t("chat.expandTrainingQuota"),
          actionHref: "/admin/pricing",
        });
        toast.error(reason);
        if (trainFileRef.current) trainFileRef.current.value = "";
        return;
      }
      patchTextTrainingCharacterCount(exactCharCount);
      setPendingFileTraining({ file, kbUuid: effectiveTrainKbUuid, title, characterCount: exactCharCount });
    } catch (error) {
      stopFileCountingProgress();
      const message = getApiErrorMessage(error) ?? t("chat.fileEstimateError");
      toast.error(message);
      patchTextTrainingUserMessage({ textTrainingOutcome: "error", textTrainingOutcomeDetail: message });
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
          if (isDuplicateContentError(error)) {
            const detail = getApiErrorMessage(error) ?? t("kb.errorDuplicateContent");
            patchTextTrainingUserMessage({
              textTrainingOutcome: "error",
              textTrainingOutcomeDetail: `${t("chat.trainingAborted")} ${detail}`,
            });
          } else {
            const detail = getApiErrorMessage(error) ?? t("chat.fileTrainingStartError");
            toast.error(detail);
            patchTextTrainingUserMessage({ textTrainingOutcome: "error", textTrainingOutcomeDetail: detail });
          }
        },
      }
    );
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const cancelPendingFileTraining = () => {
    setPendingFileTraining(null);
    patchTextTrainingUserMessage({
      textTrainingOutcome: "cancelled",
      textTrainingOutcomeDetail: t("chat.trainingAborted"),
    });
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const startTextTraining = (kbUuid: string, text: string) => {
    setActiveTrainingTitle(t("chat.textTrainingLabel"));
    startTrainingProgress(text.length);
    createTextMutation.mutate(
      { kbUuid, text },
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
          const detail = isDuplicateContentError(error)
            ? `${t("chat.trainingAborted")} ${getApiErrorMessage(error) ?? t("kb.errorDuplicateContent")}`
            : getApiErrorMessage(error) ?? t("chat.textTrainingStartError");
          patchTextTrainingUserMessage({ textTrainingOutcome: "error", textTrainingOutcomeDetail: detail });
          if (!isDuplicateContentError(error)) {
            toast.error(detail);
          }
        },
      }
    );
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
    setInputDraft("");
    appendMessage({
      role: "user",
      text: title,
      excludeFromAiContext: true,
      textTrainingPending: true,
      textTrainingCharacterCount: charCount,
    });
    const training = ((billingOverview?.usage ?? {}).training as Record<string, unknown> | undefined) ?? {};
    const limits = billingOverview?.limits ?? {};
    const used = numberValue(training.trained_chars);
    const total = numberValue(training.available_training_chars ?? limits.training_chars_available);
    if (total > 0 && Math.max(0, total - used) < charCount) {
      const reason = t("chat.fileTrainingQuotaBlocked");
      patchTextTrainingUserMessage({
        textTrainingOutcome: "error",
        textTrainingOutcomeDetail: `${t("chat.trainingCannotStart")}: ${reason}`,
      });
      appendMessage({
        role: "training-status",
        text: `${t("chat.trainingCannotStart")}: ${reason}`,
        actionLabel: t("chat.expandTrainingQuota"),
        actionHref: "/admin/pricing",
      });
      toast.error(reason);
      setTimeout(() => inputRef.current?.focus(), 50);
      return;
    }
    startTextTraining(effectiveTrainKbUuid, value);
  };

  return {
    activeTrainingRun,
    pendingTrainingConfirmation,
    trainingOperationRunning,
    onSelectTrainingFile,
    startPendingFileTraining,
    cancelPendingFileTraining,
    onSubmitTextTraining,
  };
}
