import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { sanitizeMessage } from "../../../utils/sanitize";
import ChatMessage from "../components/ChatMessage";
import api from "../../../api/axiosClient";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useAuthStore } from "../../../store/authStore";
import {
  useCreateFileIngestMutation,
  useCreateTextIngestMutation,
  useIngestRun,
  useKbList,
} from "../../knowledge-base/hooks/useKb";
import { estimateFileIngestRun } from "../../knowledge-base/services";
import {
  getTrainingFailureMessage,
  getTrainingProgress,
  isTrainingActive,
} from "../../knowledge-base/utils/trainingProgress";
import { useTranslation } from "../../../i18n";
import { useBillingAccessStatus, useBillingOverview } from "../../billing/hooks/useBilling";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../../queryKeys";

const MAX_CHAT_MESSAGES = 100;
const TRAINING_STALE_TIMEOUT_MS = 5 * 60 * 1000;
const CHAT_CONTEXT_STORAGE_KEY = "aiplaza_chat_context_notice";
const CHAT_PERSIST_PREFIX = "aiplaza_chat_persist_v2:";
/** Régi sessionStorage kulcs – egyszer átmásoljuk localStorage-ba */
const CHAT_SESSION_LEGACY_PREFIX = "aiplaza_chat_session_v1:";
function chatPersistKey(userId: number | string): string {
  return `${CHAT_PERSIST_PREFIX}${String(userId)}`;
}

function chatLegacySessionKey(userId: number | string): string {
  return `${CHAT_SESSION_LEGACY_PREFIX}${String(userId)}`;
}

type PersistedChatSession = {
  messages: ChatMessageType[];
  contextNotice: string | null;
  draft: string;
  chatMode?: "query" | "train";
  selectedChatKbUuid?: string;
  selectedTrainKbUuid?: string;
  activeTrainingRunId?: string;
  activeTrainingTitle?: string | null;
  trainingVisualProgress?: number;
  trainingStartedAt?: number | null;
  trainingEstimatedDurationMs?: number | null;
};
type ChatApiResponse = {
  answer: string;
  query_run_id?: string | null;
  answer_mode?: string;
  answer_source?: string;
  confidence?: number;
  evidence?: ChatEvidenceItem[];
  cited_claim_ids?: string[];
  cited_sentence_ids?: string[];
  cited_source_ids?: string[];
  query_profile?: Record<string, unknown>;
  matched_chunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  context_blocks?: Array<Record<string, unknown>>;
  sources?: ChatSourceItem[];
  prompt_context?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
  encoded_prompt_context?: string;
  restored_pii_spans?: RestoredPiiSpan[];
};
type ChatApiRequest = {
  question: string;
  kb_uuid?: string;
  debug?: boolean;
  conversation_history?: Array<{ role: "user" | "assistant"; content: string }>;
  retrieval_history?: string[];
};

type ChatEvidenceItem = {
  claim_id?: string;
  sentence_id?: string;
  source_id?: string;
  claim_text?: string;
  sentence_text?: string;
  [key: string]: unknown;
};

type ChatSourceItem = {
  kb_uuid: string;
  kb_name?: string;
  point_id: string;
  source_id?: string;
  title?: string;
  snippet?: string;
  source_type?: string;
  file_ref?: string | null;
  display_type?: string;
  created_by?: number | null;
  created_by_label?: string;
  created_at?: string | null;
};

type RestoredPiiSpan = {
  start: number;
  end: number;
  token?: string;
  value?: string;
  entity_type?: string;
};

export type ChatMessageType = {
  role: string;
  text: string;
  aiContextContent?: string;
  excludeFromAiContext?: boolean;
  question?: string;
  queryRunId?: string | null;
  answerMode?: string;
  answerSource?: string;
  confidence?: number;
  evidence?: ChatEvidenceItem[];
  citedClaimIds?: string[];
  citedSentenceIds?: string[];
  citedSourceIds?: string[];
  queryProfile?: Record<string, unknown>;
  matchedChunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  contextBlocks?: Array<Record<string, unknown>>;
  sources?: ChatSourceItem[];
  promptContext?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
  encodedPromptContext?: string;
  restoredPiiSpans?: RestoredPiiSpan[];
  actionLabel?: string;
  actionHref?: string;
  progressPercent?: number | null;
};

type PendingFileTraining = {
  file: File;
  kbUuid: string;
  title: string;
  characterCount: number;
};

type PendingTextTraining = {
  kbUuid: string;
  title: string;
  text: string;
};

type FileCountingProgress = {
  filename: string;
  percent: number;
  estimatedCharacters: number;
};

const MAX_CONVERSATION_CONTEXT_MESSAGES = 10;
const MAX_RETRIEVAL_HISTORY_ITEMS = 4;
const MAX_RETRIEVAL_HISTORY_CHARS = 320;

function trimToLastN(messages: ChatMessageType[], n: number): ChatMessageType[] {
  if (messages.length <= n) return messages;
  return messages.slice(-n);
}

function buildConversationHistory(messages: ChatMessageType[]): Array<{ role: "user" | "assistant"; content: string }> {
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

function buildRetrievalHistory(messages: ChatMessageType[]): string[] {
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

function isClearHistoryCommand(value: string): boolean {
  const normalized = value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return normalized === "elozmeny torlese" || normalized === "torold az elozmenyt" || normalized === "elozmenyek torlese";
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function exactTrainingCharCount(run: { metadata?: Record<string, unknown>; items?: Array<{ metadata?: Record<string, unknown> }> } | null | undefined): number {
  const total = numberValue(run?.metadata?.total_char_count);
  if (total > 0) return total;
  return (run?.items ?? []).reduce((sum, item) => sum + numberValue(item.metadata?.char_count), 0);
}

function isDuplicateOnlyTrainingRun(
  run:
    | {
        completed_count?: number;
        duplicate_count?: number;
        items?: Array<{ status?: string }>;
      }
    | null
    | undefined
): boolean {
  if (!run) return false;
  const items = run.items ?? [];
  if (items.length > 0) {
    return items.every((item) => item.status === "duplicate");
  }
  return numberValue(run.duplicate_count) > 0 && numberValue(run.completed_count) === 0;
}

function estimateFileCharactersForProgress(file: File): number {
  const name = file.name.toLowerCase();
  const multiplier = 1.3;
  if (name.endsWith(".txt")) return Math.max(1, Math.round(file.size * multiplier));
  if (name.endsWith(".pdf")) return Math.max(1, Math.round(file.size * 0.06 * multiplier));
  if (name.endsWith(".docx")) return Math.max(1, Math.round(file.size * 0.25 * multiplier));
  return Math.max(1, Math.round(file.size * 0.35 * multiplier));
}

function estimateCountingDurationMs(file: File): number {
  const mb = file.size / (1024 * 1024);
  return Math.max(1500, Math.min(15000, Math.round(1200 + mb * 1800)));
}

function estimateTrainingDurationMs(characterCount: number): number {
  const chars = Math.max(0, characterCount);
  return Math.max(20_000, Math.min(900_000, Math.round(20_000 + chars / 1.2)));
}

function estimatedTrainingProgress(elapsedMs: number, durationMs: number): number {
  const baseRatio = Math.max(0, elapsedMs / Math.max(1, durationMs));
  const ratio = Math.min(2, baseRatio);
  if (ratio <= 1) {
    const eased = 1 - Math.pow(1 - ratio, 2);
    return Math.round(6 + eased * 88);
  }
  const overtimeRatio = Math.min(1, ratio - 1);
  return Math.round(94 + overtimeRatio * 5);
}

function combineTrainingProgress(actualProgress: number, visualProgress: number): number {
  const actual = Math.max(0, Math.min(100, Math.round(actualProgress)));
  const visual = Math.max(0, Math.min(99, Math.round(visualProgress)));
  if (actual <= 0) return visual;
  if (actual >= 100) return 100;
  return Math.max(actual, visual);
}

function usagePercent(used: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((used / total) * 100)));
}

function localeTag(locale: string): string {
  if (locale === "en") return "en-GB";
  if (locale === "es") return "es-ES";
  return "hu-HU";
}

function formatCompactNumber(value: number, locale: string): string {
  return value.toLocaleString(localeTag(locale), {
    notation: value >= 10_000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  });
}

function formatInteger(value: number, locale: string): string {
  return Math.max(0, Number(value || 0)).toLocaleString(localeTag(locale));
}

function serializeProcessToTxt(
  {
    locale,
    mode,
    selectedKbLabel,
    messages,
    contextNotice,
  }: {
    locale: string;
    mode: "query" | "train";
    selectedKbLabel: string;
    messages: ChatMessageType[];
    contextNotice: string | null;
  }
): string {
  const lines: string[] = [];
  const now = new Date().toLocaleString(localeTag(locale));
  lines.push("=== AIPLAZA Chat folyamat export ===");
  lines.push(`Export időpont: ${now}`);
  lines.push(`Mód: ${mode === "train" ? "Tanítás" : "Lekérdezés"}`);
  lines.push(`Kiválasztott tudástár: ${selectedKbLabel}`);
  lines.push("");
  if (contextNotice?.trim()) {
    lines.push("=== Kontextus figyelmeztetés ===");
    lines.push(contextNotice.trim());
    lines.push("");
  }
  lines.push("=== Üzenetfolyam ===");
  messages.forEach((msg, idx) => {
    lines.push(`-- #${idx + 1} (${msg.role}) --`);
    lines.push((msg.text || "").trim() || "(üres)");
    if (msg.aiContextContent && String(msg.aiContextContent).trim() && String(msg.aiContextContent).trim() !== String(msg.text || "").trim()) {
      lines.push(`ai_context_content: ${String(msg.aiContextContent).trim()}`);
    }
    if (msg.queryRunId) lines.push(`query_run_id: ${msg.queryRunId}`);
    if (msg.answerMode) lines.push(`answer_mode: ${msg.answerMode}`);
    if (msg.answerSource) lines.push(`answer_source: ${msg.answerSource}`);
    if (typeof msg.confidence === "number") lines.push(`confidence: ${msg.confidence}`);
    if (Array.isArray(msg.sources) && msg.sources.length > 0) {
      lines.push("források:");
      msg.sources.forEach((src, srcIdx) => {
        lines.push(
          `  ${srcIdx + 1}. kb=${src.kb_name || src.kb_uuid || "-"} | source_id=${src.source_id || "-"} | title=${src.title || "-"}`
        );
      });
    }
    if (msg.promptContext && typeof msg.promptContext === "object") {
      lines.push("prompt_context:");
      lines.push(JSON.stringify(msg.promptContext, null, 2));
    }
    if (msg.debug && typeof msg.debug === "object") {
      lines.push("debug:");
      lines.push(JSON.stringify(msg.debug, null, 2));
    }
    lines.push("");
  });
  return lines.join("\n").trim();
}

function downloadTxt(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function shouldShowAnswerSources(
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

/** Üres tömb = Mind (minden tudástár); nem üres = csak a kiválasztott uuid-k. */

export default function ChatPage() {
  const { t, locale } = useTranslation();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const kbListQuery = useKbList();
  const kbList = useMemo(() => kbListQuery.data ?? [], [kbListQuery.data]);
  const { data: billingOverview } = useBillingOverview();
  const trainableKbList = useMemo(() => kbList.filter((kb) => kb.can_train === true), [kbList]);
  const selectableChatKbList = useMemo(() => kbList.filter((kb) => kb.status !== "deleted" && !kb.deleted_at), [kbList]);
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
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [chatMode, setChatMode] = useState<"query" | "train">("query");
  const [selectedChatKbUuid, setSelectedChatKbUuid] = useState("");
  const [selectedTrainKbUuid, setSelectedTrainKbUuid] = useState("");
  const [dragOverTrainFile, setDragOverTrainFile] = useState(false);
  const [contextNotice, setContextNotice] = useState<string | null>(null);
  const [inputDraft, setInputDraft] = useState("");
  const [fileEstimateLoading, setFileEstimateLoading] = useState(false);
  const [fileCountingProgress, setFileCountingProgress] = useState<FileCountingProgress | null>(null);
  const [pendingFileTraining, setPendingFileTraining] = useState<PendingFileTraining | null>(null);
  const [pendingTextTraining, setPendingTextTraining] = useState<PendingTextTraining | null>(null);
  const [activeTrainingRunId, setActiveTrainingRunId] = useState<string | undefined>(undefined);
  const [activeTrainingTitle, setActiveTrainingTitle] = useState<string | null>(null);
  const [trainingVisualProgress, setTrainingVisualProgress] = useState(0);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const trainFileRef = useRef<HTMLInputElement | null>(null);
  /** Üres kezdőállapot ne írja felül a mentett beszélgetést (layout után engedélyezzük a mentést) */
  const persistEnabledRef = useRef(false);
  /** Utolsó ismert user id – unmount/pagehide mentéshez, ha a store már null */
  const lastUserIdRef = useRef<number | string | null>(null);
  const messagesRef = useRef<ChatMessageType[]>(messages);
  const contextNoticeRef = useRef<string | null>(contextNotice);
  const inputDraftRef = useRef(inputDraft);
  const chatModeRef = useRef<"query" | "train">(chatMode);
  const selectedChatKbUuidRef = useRef(selectedChatKbUuid);
  const selectedTrainKbUuidRef = useRef(selectedTrainKbUuid);
  const fileCountingTimerRef = useRef<number | null>(null);
  const trainingProgressTimerRef = useRef<number | null>(null);
  const activeTrainingRunIdRef = useRef<string | undefined>(activeTrainingRunId);
  const activeTrainingTitleRef = useRef<string | null>(activeTrainingTitle);
  const trainingVisualProgressRef = useRef(trainingVisualProgress);
  const trainingStartedAtRef = useRef<number | null>(null);
  const trainingEstimatedDurationMsRef = useRef<number | null>(null);
  const staleTrainingTimeoutRef = useRef<number | null>(null);
  messagesRef.current = messages;
  contextNoticeRef.current = contextNotice;
  inputDraftRef.current = inputDraft;
  chatModeRef.current = chatMode;
  selectedChatKbUuidRef.current = selectedChatKbUuid;
  selectedTrainKbUuidRef.current = selectedTrainKbUuid;
  activeTrainingRunIdRef.current = activeTrainingRunId;
  activeTrainingTitleRef.current = activeTrainingTitle;
  trainingVisualProgressRef.current = trainingVisualProgress;
  if (user?.id != null) lastUserIdRef.current = user.id;

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
        activeTrainingRunId: activeTrainingRunIdRef.current,
        activeTrainingTitle: activeTrainingTitleRef.current,
        trainingVisualProgress: trainingVisualProgressRef.current,
        trainingStartedAt: trainingStartedAtRef.current,
        trainingEstimatedDurationMs: trainingEstimatedDurationMsRef.current,
      };
      localStorage.setItem(chatPersistKey(id), JSON.stringify(payload));
    } catch {
      // storage optional
    }
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (!user?.id) {
      persistEnabledRef.current = false;
      return;
    }
    persistEnabledRef.current = false;
    try {
      let raw = localStorage.getItem(chatPersistKey(user.id));
      if (!raw) {
        const legacy = sessionStorage.getItem(chatLegacySessionKey(user.id));
        if (legacy) {
          raw = legacy;
          localStorage.setItem(chatPersistKey(user.id), legacy);
          sessionStorage.removeItem(chatLegacySessionKey(user.id));
        }
      }
      if (raw) {
        const data = JSON.parse(raw) as Partial<PersistedChatSession>;
        if (Array.isArray(data.messages)) {
          setMessages(trimToLastN(data.messages as ChatMessageType[], MAX_CHAT_MESSAGES));
        }
        if ("contextNotice" in data && (data.contextNotice === null || typeof data.contextNotice === "string")) {
          setContextNotice(data.contextNotice);
        } else {
          const saved = localStorage.getItem(CHAT_CONTEXT_STORAGE_KEY);
          if (saved) setContextNotice(saved);
        }
        if (typeof data.draft === "string") setInputDraft(data.draft);
        if (data.chatMode === "query" || data.chatMode === "train") setChatMode(data.chatMode);
        if (typeof data.selectedChatKbUuid === "string") setSelectedChatKbUuid(data.selectedChatKbUuid);
        if (typeof data.selectedTrainKbUuid === "string") setSelectedTrainKbUuid(data.selectedTrainKbUuid);
        if (typeof data.activeTrainingRunId === "string" && data.activeTrainingRunId.trim()) {
          setActiveTrainingRunId(data.activeTrainingRunId);
        }
        if (typeof data.activeTrainingTitle === "string") {
          setActiveTrainingTitle(data.activeTrainingTitle);
        }
        if (typeof data.trainingVisualProgress === "number") {
          setTrainingVisualProgress(Math.max(0, Math.min(99, Math.round(data.trainingVisualProgress))));
        }
        trainingStartedAtRef.current = typeof data.trainingStartedAt === "number" ? data.trainingStartedAt : null;
        trainingEstimatedDurationMsRef.current =
          typeof data.trainingEstimatedDurationMs === "number" ? data.trainingEstimatedDurationMs : null;
      } else {
        const saved = localStorage.getItem(CHAT_CONTEXT_STORAGE_KEY);
        if (saved) setContextNotice(saved);
      }
    } catch {
      // storage optional
    } finally {
      persistEnabledRef.current = true;
    }
  }, [user?.id]);

  useEffect(() => {
    if (!user?.id || !persistEnabledRef.current) return;
    flushPersistToDisk();
  }, [
    user?.id,
    messages,
    contextNotice,
    inputDraft,
    chatMode,
    selectedChatKbUuid,
    selectedTrainKbUuid,
    activeTrainingRunId,
    activeTrainingTitle,
    trainingVisualProgress,
    flushPersistToDisk,
  ]);

  /** Lap elhagyása / frissítés / háttér: szinkron mentés (a passzív effect késő lehet) */
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
    if (!kbListQuery.isFetched) return;
    if (!trainableKbList.length) {
      setSelectedTrainKbUuid("");
      return;
    }
    if (trainableKbList.some((kb) => kb.uuid === selectedTrainKbUuid)) return;
    setSelectedTrainKbUuid(trainableKbList[0].uuid);
  }, [kbListQuery.isFetched, selectedTrainKbUuid, trainableKbList]);

  useEffect(() => {
    if (!kbListQuery.isFetched) return;
    if (selectableChatKbList.length === 1) {
      if (selectedChatKbUuid !== selectableChatKbList[0].uuid) {
        setSelectedChatKbUuid(selectableChatKbList[0].uuid);
      }
      return;
    }
    if (!selectedChatKbUuid) return;
    if (selectableChatKbList.some((kb) => kb.uuid === selectedChatKbUuid)) return;
    setSelectedChatKbUuid("");
  }, [kbListQuery.isFetched, selectableChatKbList, selectedChatKbUuid]);

  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => (isTrainingActive(state.data?.status) ? 1500 : 4000),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const trainingProgress = useMemo(() => getTrainingProgress(activeTrainingRun), [activeTrainingRun]);
  const displayedTrainingProgress = combineTrainingProgress(trainingProgress, trainingVisualProgress);
  const pendingTrainingConfirmation = pendingFileTraining !== null || pendingTextTraining !== null;
  const trainingOperationRunning =
    fileEstimateLoading ||
    createTextMutation.isPending ||
    createFileMutation.isPending ||
    isTrainingActive(activeTrainingRun?.status);
  const effectiveTrainKbUuid = selectedTrainKbUuid || trainableKbList[0]?.uuid || "";
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
  const appendMessage = useCallback((msg: ChatMessageType) => {
    setMessages((prev) => {
      const next = trimToLastN([...prev, msg], MAX_CHAT_MESSAGES);
      return next;
    });
  }, []);
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
    [stopFileCountingProgress]
  );
  const stopTrainingProgress = useCallback(() => {
    if (trainingProgressTimerRef.current !== null) {
      window.clearInterval(trainingProgressTimerRef.current);
      trainingProgressTimerRef.current = null;
    }
    trainingStartedAtRef.current = null;
    trainingEstimatedDurationMsRef.current = null;
  }, []);
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
    [stopTrainingProgress]
  );
  const refreshBillingCounters = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
  }, [queryClient]);
  const refreshKnowledgeBaseList = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.kb });
  }, [queryClient]);

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
  }, [activeTrainingRunId, activeTrainingTitle]);

  useEffect(() => {
    try {
      if (contextNotice) {
        localStorage.setItem(CHAT_CONTEXT_STORAGE_KEY, contextNotice);
      } else {
        localStorage.removeItem(CHAT_CONTEXT_STORAGE_KEY);
      }
    } catch {
      // localStorage optional
    }
  }, [contextNotice]);

  useEffect(() => {
    clearStaleTrainingTimeout();
    if (!activeTrainingRunId || !activeTrainingRun || !isTrainingActive(activeTrainingRun.status)) {
      return;
    }
    const lastUpdatedRaw = activeTrainingRun.updated_at || activeTrainingRun.started_at || activeTrainingRun.created_at;
    const lastUpdatedAtMs = Date.parse(lastUpdatedRaw);
    const ageMs = Number.isFinite(lastUpdatedAtMs) ? Math.max(0, Date.now() - lastUpdatedAtMs) : 0;
    const waitMs = Math.max(10_000, TRAINING_STALE_TIMEOUT_MS - ageMs);
    staleTrainingTimeoutRef.current = window.setTimeout(() => {
      appendMessage({
        role: "training-status",
        text: t("chat.trainingStaleWarning"),
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
    refreshBillingCounters,
    refreshKnowledgeBaseList,
    stopTrainingProgress,
    t,
  ]);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRun) return;
    if (isTrainingActive(activeTrainingRun.status)) {
      return;
    }

    if (activeTrainingRun.status === "completed" || activeTrainingRun.status === "partial_success") {
      const u = useAuthStore.getState().user;
      if (u && u.tenant_kb_has_training !== true) {
        setUser({ ...u, tenant_kb_has_training: true });
      }
      if (isDuplicateOnlyTrainingRun(activeTrainingRun)) {
        appendMessage({
          role: "training-status",
          text: t("chat.trainingAlreadyLoaded"),
        });
      } else {
        const exactCharText = exactTrainingCharCount(activeTrainingRun);
        const exactCharMessage =
          exactCharText > 0 ? ` ${t("chat.fileCharacterCount").replace("{{count}}", formatInteger(exactCharText, locale))}` : "";
        appendMessage({
          role: "training-status",
          text: `Tanítás: ${
            activeTrainingRun.status === "partial_success"
              ? t("chat.trainingStatusPartialSuccess")
              : t("chat.trainingStatusCompleted")
          } 100%.${exactCharMessage}`,
        });
      }
      refreshKnowledgeBaseList();
    } else {
      appendMessage({
        role: "assistant",
        text: getTrainingFailureMessage(activeTrainingRun, t) ?? t("chat.trainingFailed"),
      });
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
    refreshBillingCounters,
    refreshKnowledgeBaseList,
    setUser,
    locale,
    stopTrainingProgress,
    t,
  ]);

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRunQuery.isError) return;
    appendMessage({
      role: "assistant",
      text: getApiErrorMessage(activeTrainingRunQuery.error) ?? t("chat.trainingFailed"),
    });
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
    refreshBillingCounters,
    stopTrainingProgress,
    t,
  ]);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setContextNotice(null);
    setInputDraft("");
    setPendingFileTraining(null);
    setPendingTextTraining(null);
    try {
      localStorage.removeItem(CHAT_CONTEXT_STORAGE_KEY);
      const id = useAuthStore.getState().user?.id;
      if (id) {
        sessionStorage.removeItem(chatLegacySessionKey(id));
      }
    } catch {
      // storage optional
    }
  }, []);

  const exportChatProcess = useCallback(() => {
    const content = serializeProcessToTxt({
      locale,
      mode: chatMode,
      selectedKbLabel: selectedTopKbLabel,
      messages: messagesRef.current,
      contextNotice: contextNoticeRef.current,
    });
    const stamp = new Date().toISOString().replace(/[:]/g, "-").replace(/\..+$/, "");
    downloadTxt(`aiplaza-chat-folyamat-${stamp}.txt`, `${content}\n`);
    toast.success("A folyamat exportálva lett .txt fájlba.");
  }, [locale, chatMode, selectedTopKbLabel]);

  const send = useCallback(async () => {
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
      const dedupedResponseSources = responseSources.filter((item, index, all) => {
        const titleKey = String(item?.title || "").trim().toLowerCase().replace(/\s+/g, " ");
        const snippetKey = String(item?.snippet || "").trim().toLowerCase().replace(/\s+/g, " ");
        const typeKey = String(item?.display_type || item?.source_type || "").trim().toLowerCase();
        const fallbackKey = String(item?.source_id || item?.point_id || "").trim().toLowerCase();
        const isChatTextTraining =
          String(item?.source_type || "").trim().toLowerCase() === "text" &&
          (titleKey.includes("chatből tanított szöveg") || typeKey.includes("gépel") || typeKey.includes("gepel"));
        const composite = (isChatTextTraining && snippetKey ? `${snippetKey}|text` : `${titleKey}|${snippetKey}|${typeKey}`).replace(
          /^\|+\|*$/,
          fallbackKey
        );
        return all.findIndex((candidate) => {
          const candidateTitleKey = String(candidate?.title || "").trim().toLowerCase().replace(/\s+/g, " ");
          const candidateSnippetKey = String(candidate?.snippet || "").trim().toLowerCase().replace(/\s+/g, " ");
          const candidateTypeKey = String(candidate?.display_type || candidate?.source_type || "").trim().toLowerCase();
          const candidateFallbackKey = String(candidate?.source_id || candidate?.point_id || "").trim().toLowerCase();
          const candidateIsChatTextTraining =
            String(candidate?.source_type || "").trim().toLowerCase() === "text" &&
            (candidateTitleKey.includes("chatből tanított szöveg") || candidateTypeKey.includes("gépel") || candidateTypeKey.includes("gepel"));
          const candidateComposite = (
            candidateIsChatTextTraining && candidateSnippetKey
              ? `${candidateSnippetKey}|text`
              : `${candidateTitleKey}|${candidateSnippetKey}|${candidateTypeKey}`
          ).replace(/^\|+\|*$/, candidateFallbackKey);
          return candidateComposite === composite;
        }) === index;
      });
      const sources = shouldShowAnswerSources(data, answer, t("chat.insufficientInfo"), responseSources.length)
        ? dedupedResponseSources
        : [];
      const encodedQuestionForHistory = String(
        (data?.prompt_context && typeof data.prompt_context === "object"
          ? (data.prompt_context as Record<string, unknown>).encoded_latest_question
          : "") || question
      ).trim();
      const encodedAnswerForHistory = String(
        (data?.prompt_context && typeof data.prompt_context === "object"
          ? (data.prompt_context as Record<string, unknown>).encoded_answer_text
          : "") || answer
      ).trim();
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
  }, [appendMessage, clearHistory, loading, billingRestricted, inputDraft, flushPersistToDisk, effectiveChatKbUuid, refreshBillingCounters, t]);

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
      {
        kbUuid: pending.kbUuid,
        title: pending.title,
        text: pending.text,
      },
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
    setPendingTextTraining({
      kbUuid: effectiveTrainKbUuid,
      title: t("chat.textTrainingTitle"),
      text: value,
    });
  };

  if (billingRestricted) {
    return (
      <div className="flex-1 bg-[var(--color-background)] px-6 py-10 text-[var(--color-foreground)]">
        <div className="mx-auto flex min-h-[60vh] max-w-lg items-center justify-center text-center">
          <div className="rounded-3xl border border-[var(--color-danger-border)] bg-[var(--color-danger-bg)] p-8 text-[var(--color-danger-text)] shadow-sm">
            <h1 className="text-2xl font-semibold">
              {freeTrialExpired ? t("billing.chatUnavailableTrialExpired") : t("billing.chatUnavailablePayment")}
            </h1>
            {freeTrialExpired ? (
              <>
                <p className="mt-3 text-sm leading-relaxed">{t("billing.chatUnavailableTrialExpiredHint")}</p>
                <a
                  href="/admin/csomagok"
                  className="mt-5 inline-flex rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] hover:opacity-90"
                >
                  {t("billing.choosePackageCta")}
                </a>
              </>
            ) : (
              <a
                href="/admin/szamlak/kiegyenlites"
                className="mt-5 inline-flex rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] hover:opacity-90"
              >
                {t("billing.settlePayment")}
              </a>
            )}
          </div>
        </div>
      </div>
    );
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
              {contextNotice ? (
                <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
                  <div className="flex w-full justify-start">
                    <ChatMessage role="assistant" text={contextNotice} />
                  </div>
                </div>
              ) : null}
              {messages.length > 0 ? (
                <div className="space-y-1">
                  {messages.map((msg, index) => (
                    <div key={`${msg.role}-${index}`} className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
                      <div
                        className={`flex w-full ${
                          msg.role === "user" || msg.role === "training-status" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <ChatMessage
                          role={msg.role}
                          text={msg.text}
                          question={msg.question}
                          queryRunId={msg.queryRunId}
                          answerMode={msg.answerMode}
                          answerSource={msg.answerSource}
                          confidence={msg.confidence}
                          evidence={msg.evidence}
                          citedClaimIds={msg.citedClaimIds}
                          citedSentenceIds={msg.citedSentenceIds}
                          citedSourceIds={msg.citedSourceIds}
                          queryProfile={msg.queryProfile}
                          matchedChunks={msg.matchedChunks}
                          claims={msg.claims}
                          contextBlocks={msg.contextBlocks}
                          actionLabel={msg.actionLabel}
                          actionHref={msg.actionHref}
                          progressPercent={msg.progressPercent}
                          sources={msg.sources}
                          promptContext={msg.promptContext}
                          debug={msg.debug}
                          encodedPromptContext={msg.encodedPromptContext}
                          restoredPiiSpans={msg.restoredPiiSpans}
                        />
                      </div>
                    </div>
                  ))}
                  {fileCountingProgress ? (
                    <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
                      <div className="flex w-full items-center justify-end gap-2">
                        <span className="text-xs font-medium text-[var(--color-muted)]">Beolvasás</span>
                        <div className="mr-4 h-1 w-[120px] overflow-hidden rounded-full bg-[var(--color-border)]">
                          <div
                            className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
                            style={{ width: `${Math.max(0, Math.min(100, Math.round(fileCountingProgress.percent)))}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {activeTrainingTitle ? (
                    <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
                      <div className="flex w-full justify-end">
                        <div className="mr-4 flex w-[120px] flex-col items-center gap-1">
                          <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--color-border)]">
                            <div
                              className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
                              style={{ width: `${Math.max(0, Math.min(100, Math.round(displayedTrainingProgress)))}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-[var(--color-muted)]">
                            Tanítás {Math.max(0, Math.min(100, Math.round(displayedTrainingProgress)))}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {pendingFileTraining || pendingTextTraining ? (
                    <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
                      <div className="flex w-full justify-end gap-2">
                        <button
                          type="button"
                          onClick={pendingFileTraining ? cancelPendingFileTraining : cancelPendingTextTraining}
                          className="rounded-full border border-[var(--color-border)] bg-transparent px-3 py-1 text-xs font-medium text-[var(--color-muted)] hover:bg-[var(--color-border)]/20"
                        >
                          {t("chat.trainingStartCancel")}
                        </button>
                        <button
                          type="button"
                          onClick={pendingFileTraining ? startPendingFileTraining : startPendingTextTraining}
                          className="rounded-full bg-[var(--color-primary)] px-3 py-1 text-xs font-medium text-[var(--color-on-primary)] hover:opacity-90"
                        >
                          {t("chat.trainingStartConfirm")}
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <div ref={messagesEndRef} />
                </div>
              ) : null}

              {messages.length === 0 ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-[var(--color-muted)] text-sm leading-6 pointer-events-none">
                  <div className="max-w-lg whitespace-pre-line">{t("chat.emptyState")}</div>
                </div>
              ) : null}

              {loading && (
                <div className="mx-auto flex max-w-3xl justify-start pt-2 pb-2">
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] px-4 py-2 text-[var(--color-muted)] animate-pulse">
                    ...
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input sor: chat mező + vezérlők */}
          <input
            ref={trainFileRef}
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="hidden"
            onChange={(e) => onSelectTrainingFile(e.target.files?.[0] ?? null)}
          />
          <div className="shrink-0 w-full bg-[var(--color-background)] px-4 pt-[18px] pb-2">
            <div
              className={`relative mx-auto h-28 max-w-3xl overflow-hidden rounded-[32px] border bg-[var(--color-card)] ${
                chatMode === "train" && dragOverTrainFile
                  ? "border-[var(--color-primary)]"
                  : "border-[var(--color-border)]"
              }`}
              onDragOver={(event) => {
                if (chatMode !== "train") return;
                event.preventDefault();
                event.stopPropagation();
                setDragOverTrainFile(true);
              }}
              onDragLeave={(event) => {
                if (chatMode !== "train") return;
                event.preventDefault();
                event.stopPropagation();
                setDragOverTrainFile(false);
              }}
              onDrop={(event) => {
                if (chatMode !== "train") return;
                event.preventDefault();
                event.stopPropagation();
                setDragOverTrainFile(false);
                onSelectTrainingFile(event.dataTransfer?.files?.[0] ?? null);
              }}
            >
              <div className="pointer-events-none absolute bottom-3 right-3 z-10 flex items-center gap-2">
                {chatMode !== "train" && messages.length > 0 ? (
                  <button
                    type="button"
                    onClick={clearHistory}
                    className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] bg-transparent text-[var(--color-muted)] transition hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                    aria-label={t("chat.newChat")}
                    title={t("chat.newChat")}
                  >
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M6.5 4.5h8l3 3v11c0 .6-.4 1-1 1h-10c-.6 0-1-.4-1-1v-13c0-.6.4-1 1-1Z"
                        fill="white"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M14.5 4.5v3h3M9 15.5l.5-2.2 5.7-5.7c.5-.5 1.3-.5 1.8 0s.5 1.3 0 1.8l-5.7 5.7-2.3.4Z"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                ) : null}
                {chatMode === "train" ? (
                  <button
                    type="button"
                    onClick={() => trainFileRef.current?.click()}
                    disabled={trainingOperationRunning || pendingTrainingConfirmation}
                    className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border transition ${
                      trainingOperationRunning || pendingTrainingConfirmation
                        ? "cursor-not-allowed border-[var(--color-border)] text-[var(--color-muted)] opacity-50"
                        : "border-[var(--color-border)] bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                    }`}
                    aria-label={t("chat.selectTrainingFile")}
                    title={t("chat.selectTrainingFile")}
                  >
                    <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M12 16V5m0 0 4 4m-4-4-4 4M5 16.5V18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2v-1.5"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={exportChatProcess}
                  disabled={messages.length === 0 && !contextNotice}
                  className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full border transition ${
                    messages.length === 0 && !contextNotice
                      ? "cursor-not-allowed border-[var(--color-border)] text-[var(--color-muted)] opacity-50"
                      : "border-[var(--color-border)] bg-transparent text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                  }`}
                  aria-label="Folyamat exportálása (.txt)"
                  title="Folyamat exportálása (.txt)"
                >
                  <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M5 4.5h11l3 3V19a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 19V6a1.5 1.5 0 0 1 1-1.5Z"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M9 4.5V9h6V4.5M8 14h8M8 17h5"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={chatMode === "train" ? onSubmitTextTraining : send}
                  disabled={loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))}
                  className={`pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold leading-none transition ${
                    loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))
                      ? "cursor-not-allowed bg-[var(--color-border)] text-[var(--color-muted)]"
                      : "bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
                  }`}
                  aria-label={chatMode === "train" ? t("chat.startTraining") : t("chat.sendQuestion")}
                >
                  ↑
                </button>
              </div>
              <input
                type="text"
                ref={inputRef}
                value={inputDraft}
                onChange={(e) => setInputDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (chatMode === "train") {
                      onSubmitTextTraining();
                    } else {
                      send();
                    }
                  }
                }}
                className="chat-question-input chat-composer-input w-full h-14 min-h-0 overflow-hidden bg-transparent text-[var(--color-foreground)] rounded-[999px] box-border text-base leading-none !py-0 !pl-5 pr-5"
                placeholder={
                  chatMode === "train"
                    ? t("chat.trainPlaceholder")
                    : t("chat.queryPlaceholder")
                }
                disabled={loading || (chatMode === "train" && trainingOperationRunning)}
              />
              <div className="absolute bottom-3 left-3 right-14 flex items-center gap-2 overflow-visible">
                <div className="relative rounded-full bg-neutral-700 pl-1.5 pr-4">
                  <select
                    value={chatMode}
                    onChange={(event) => setChatMode(event.target.value === "train" ? "train" : "query")}
                    className="!h-8 !w-auto appearance-none !rounded-full !border-0 !bg-transparent !py-0 pl-0 pr-7 text-xs font-medium leading-none !text-gray-100 !shadow-none focus:!border-0 focus:!bg-transparent focus:!text-gray-100 focus:!shadow-none focus:!ring-0 active:!bg-transparent"
                    aria-label={t("chat.chatModeLabel")}
                  >
                    <option value="query">{t("chat.modeQuery")}</option>
                    <option value="train">{t("chat.modeTrain")}</option>
                  </select>
                  <span className="pointer-events-none absolute right-3 top-1/2 h-1.5 w-1.5 -translate-y-[65%] rotate-45 border-b border-r border-white/80" />
                </div>
                <div className="relative inline-flex min-w-0 items-center">
                  <span className="max-w-[240px] truncate text-xs font-bold leading-5 text-[var(--color-foreground)]">
                    {selectedTopKbLabel}
                  </span>
                  <span className="ml-[5px] h-1.5 w-1.5 -translate-y-[1px] rotate-45 border-b border-r border-[var(--color-muted)]" />
                  <select
                    value={selectedTopKbUuid}
                    onChange={(event) => {
                      if (chatMode === "train") {
                        setSelectedTrainKbUuid(event.target.value);
                      } else {
                        setSelectedChatKbUuid(event.target.value);
                      }
                    }}
                    className="absolute inset-0 !h-full !w-full cursor-pointer appearance-none !rounded-none !border-0 !bg-transparent !p-0 opacity-0 !shadow-none focus:!border-0 focus:!shadow-none focus:!ring-0"
                    disabled={loading || (chatMode === "train" && (trainingOperationRunning || pendingTrainingConfirmation))}
                    aria-label={t("chat.kbSelectorLabel")}
                  >
                    {chatMode === "query" && selectableChatKbList.length > 1 ? (
                      <option value="">{t("chat.allKbs")}</option>
                    ) : null}
                    {(chatMode === "train" ? trainableKbList : selectableChatKbList).map((kb) => (
                      <option key={kb.uuid} value={kb.uuid}>
                        {kb.name}
                      </option>
                    ))}
                  </select>
                </div>
                {composerUsage ? (
                  <div
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-muted)]"
                    title={composerUsage.title}
                    aria-label={composerUsage.label}
                  >
                    <svg className="h-5 w-5 -rotate-90" viewBox="0 0 20 20" aria-hidden="true">
                      <circle
                        cx="10"
                        cy="10"
                        r="7"
                        fill="none"
                        stroke="var(--color-border)"
                        strokeWidth="2.5"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="7"
                        fill="none"
                        stroke="var(--color-primary)"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeDasharray={`${(composerUsage.percent / 100) * 43.98} 43.98`}
                      />
                    </svg>
                    <span className="max-w-[160px] truncate">{composerUsage.label}</span>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
