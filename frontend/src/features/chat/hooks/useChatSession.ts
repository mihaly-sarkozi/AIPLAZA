import { useEffect, useMemo } from "react";

import { formatCompactNumber, numberValue, usagePercent } from "../utils/chatNumbers";

type KnowledgeBaseOption = {
  uuid: string;
  name: string;
  status?: string | null;
  deleted_at?: string | null;
  can_train?: boolean;
};

type UseChatSessionOptions = {
  kbList: KnowledgeBaseOption[];
  kbListFetched: boolean;
  billingOverview: { usage?: Record<string, unknown>; limits?: Record<string, unknown> } | null | undefined;
  chatMode: "query" | "train";
  selectedChatKbUuid: string;
  selectedTrainKbUuid: string;
  setChatMode: (mode: "query" | "train") => void;
  setSelectedChatKbUuid: (value: string) => void;
  setSelectedTrainKbUuid: (value: string) => void;
  locale: string;
  t: (key: string) => string;
};

export function useChatSession({
  kbList,
  kbListFetched,
  billingOverview,
  chatMode,
  selectedChatKbUuid,
  selectedTrainKbUuid,
  setChatMode,
  setSelectedChatKbUuid,
  setSelectedTrainKbUuid,
  locale,
  t,
}: UseChatSessionOptions) {
  const trainableKbList = useMemo(() => kbList.filter((kb) => kb.can_train === true), [kbList]);
  const selectableChatKbList = useMemo(() => kbList.filter((kb) => kb.status !== "deleted" && !kb.deleted_at), [kbList]);

  useEffect(() => {
    if (!kbListFetched) return;
    if (!trainableKbList.length) {
      setSelectedTrainKbUuid("");
      if (chatMode === "train") setChatMode("query");
      return;
    }
    if (trainableKbList.some((kb) => kb.uuid === selectedTrainKbUuid)) return;
    setSelectedTrainKbUuid(trainableKbList[0].uuid);
  }, [chatMode, kbListFetched, selectedTrainKbUuid, setChatMode, setSelectedTrainKbUuid, trainableKbList]);

  useEffect(() => {
    if (!kbListFetched) return;
    if (selectableChatKbList.length === 1) {
      if (selectedChatKbUuid !== selectableChatKbList[0].uuid) {
        setSelectedChatKbUuid(selectableChatKbList[0].uuid);
      }
      return;
    }
    if (!selectedChatKbUuid) return;
    if (selectableChatKbList.some((kb) => kb.uuid === selectedChatKbUuid)) return;
    setSelectedChatKbUuid("");
  }, [kbListFetched, selectableChatKbList, selectedChatKbUuid, setSelectedChatKbUuid]);

    const effectiveTrainKbUuid = trainableKbList.some((kb) => kb.uuid === selectedTrainKbUuid)
      ? selectedTrainKbUuid
      : trainableKbList[0]?.uuid ?? "";
  const effectiveChatKbUuid = selectableChatKbList.some((kb) => kb.uuid === selectedChatKbUuid) ? selectedChatKbUuid : "";
  const selectedTopKbUuid = chatMode === "train" ? effectiveTrainKbUuid : effectiveChatKbUuid;
  const selectedTopKbLabel = useMemo(() => {
    if (chatMode === "query" && !selectedTopKbUuid) return t("chat.allKbs");
    const options = chatMode === "train" ? trainableKbList : selectableChatKbList;
    return options.find((kb) => kb.uuid === selectedTopKbUuid)?.name ?? t("chat.kbFallback");
  }, [chatMode, selectedTopKbUuid, selectableChatKbList, t, trainableKbList]);

  const composerUsage = useMemo(() => {
    const usage = billingOverview?.usage ?? {};
    const limits = billingOverview?.limits ?? {};
    if (chatMode === "train") {
      const training = (usage.training as Record<string, unknown> | undefined) ?? {};
      const used = numberValue(training.trained_chars);
      const total = numberValue(training.available_training_chars ?? limits.training_chars_available);
      if (total <= 0) return null;
      const count = `${formatCompactNumber(used, locale)} / ${formatCompactNumber(total, locale)}`;
      return {
        percent: usagePercent(used, total),
        label: t("chat.usageTrainingCharsRemaining").replace("{{count}}", count),
        title: `${formatCompactNumber(used, locale)} / ${formatCompactNumber(total, locale)}`,
      };
    }

    const questions = (usage.questions as Record<string, unknown> | undefined) ?? {};
    const used = numberValue(questions.used_total);
    const total = numberValue(questions.available_total);
    if (total <= 0) return null;
    const count = `${formatCompactNumber(used, locale)} / ${formatCompactNumber(total, locale)}`;
    return {
      percent: usagePercent(used, total),
      label: t("chat.usageQuestionsRemaining").replace("{{count}}", count),
      title: `${formatCompactNumber(used, locale)} / ${formatCompactNumber(total, locale)}`,
    };
  }, [billingOverview, chatMode, locale, t]);

  return {
    trainableKbList,
    selectableChatKbList,
    effectiveTrainKbUuid,
    effectiveChatKbUuid,
    selectedTopKbUuid,
    selectedTopKbLabel,
    composerUsage,
  };
}
