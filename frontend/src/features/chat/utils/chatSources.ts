import type { ChatApiResponse, ChatSourceItem } from "../types";

export function shouldShowAnswerSources(
  data: ChatApiResponse,
  answer: string,
  insufficientInfoText: string,
  sourceCount: number
): boolean {
  if (sourceCount > 0) return true;
  const answerMode = String(data?.answer_mode || "").trim();
  const answerSource = String(data?.answer_source || "").trim();
  if (!answer.trim() || answer.trim() === insufficientInfoText.trim()) return false;
  if (!answerMode || answerMode === "no_answer") return false;
  if (answerSource === "none" || answerSource === "llm_fallback") return false;
  return true;
}

function sourceDedupKey(item: ChatSourceItem): string {
  const titleKey = String(item?.title || "").trim().toLowerCase().replace(/\s+/g, " ");
  const snippetKey = String(item?.snippet || "").trim().toLowerCase().replace(/\s+/g, " ");
  const typeKey = String(item?.display_type || item?.source_type || "").trim().toLowerCase();
  const fallbackKey = String(item?.source_id || item?.point_id || "").trim().toLowerCase();
  const isChatTextTraining =
    String(item?.source_type || "").trim().toLowerCase() === "text" &&
    (titleKey.includes("chatből tanított szöveg") || typeKey.includes("gépel") || typeKey.includes("gepel"));
  return (isChatTextTraining && snippetKey ? `${snippetKey}|text` : `${titleKey}|${snippetKey}|${typeKey}`).replace(
    /^\|+\|*$/,
    fallbackKey
  );
}

export function dedupeChatSources(sources: ChatSourceItem[]): ChatSourceItem[] {
  return sources.filter((item, index, all) => {
    const composite = sourceDedupKey(item);
    return all.findIndex((candidate) => sourceDedupKey(candidate) === composite) === index;
  });
}

export function getEncodedHistoryText(
  data: ChatApiResponse,
  field: "encoded_latest_question" | "encoded_answer_text",
  fallback: string
): string {
  return String(
    (data?.prompt_context && typeof data.prompt_context === "object"
      ? (data.prompt_context as Record<string, unknown>)[field]
      : "") || fallback
  ).trim();
}
