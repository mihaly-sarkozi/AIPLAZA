import { useEffect, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";
import { toast } from "sonner";

import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { sanitizeMessage } from "../../../utils/sanitize";
import { useCreateFileIngestMutation, useCreateTextIngestMutation, useIngestRun } from "../../knowledge-base/hooks/useKb";
import { estimateFileIngestRun } from "../../knowledge-base/services";
import { isTrainingActive } from "../../knowledge-base/utils/trainingProgress";
import type { ChatMessageType, FileCountingProgress, PendingFileTraining, PendingTextTraining } from "../types";
import { formatInteger, numberValue } from "../utils/chatNumbers";
import { useTrainingProgressTimers } from "./useTrainingProgressTimers";
import { useTrainingRunEffects } from "./useTrainingRunEffects";

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
    locale,
    inputRef,
    trainingStartedAtRef,
    trainingEstimatedDurationMsRef,
    setUser,
    appendMessage,
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
          actionHref: "/admin/pricing",
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
        actionHref: "/admin/pricing",
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
