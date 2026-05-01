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
import {
  getTrainingFailureMessage,
  getTrainingProgress,
  getTrainingStatusDetail,
  getTrainingStatusLabel,
  isTrainingActive,
} from "../../knowledge-base/utils/trainingProgress";
import { useTranslation } from "../../../i18n";

const MAX_CHAT_MESSAGES = 100;
const CHAT_CONTEXT_STORAGE_KEY = "aiplaza_chat_context_notice";
const CHAT_PERSIST_PREFIX = "aiplaza_chat_persist_v2:";
const MAX_CONVERSATION_CONTEXT_MESSAGES = 30;
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
  debug?: Record<string, unknown> | null;
};
type ChatApiRequest = {
  question: string;
  kb_uuid?: string;
  debug?: boolean;
  conversation_history?: Array<{ role: "user" | "assistant"; content: string }>;
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
  point_id: string;
  source_id?: string;
  title?: string;
  snippet?: string;
  source_type?: string;
  file_ref?: string | null;
  display_type?: string;
  created_by?: number | null;
  created_by_label?: string;
};

export type ChatMessageType = {
  role: string;
  text: string;
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
  debug?: Record<string, unknown> | null;
};

function trimToLastN(messages: ChatMessageType[], n: number): ChatMessageType[] {
  if (messages.length <= n) return messages;
  return messages.slice(-n);
}

function isClearHistoryCommand(value: string): boolean {
  const normalized = value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return normalized === "elozmeny torlese" || normalized === "torold az elozmenyt" || normalized === "elozmenyek torlese";
}

function buildConversationHistory(messages: ChatMessageType[]): Array<{ role: "user" | "assistant"; content: string }> {
  return messages
    .filter((message) => (message.role === "user" || message.role === "assistant") && message.text.trim())
    .slice(-MAX_CONVERSATION_CONTEXT_MESSAGES)
    .map((message) => ({
      role: message.role === "user" ? "user" : "assistant",
      content: message.text.trim(),
    }));
}

/** Üres tömb = Mind (minden tudástár); nem üres = csak a kiválasztott uuid-k. */

export default function ChatPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const { data: kbList = [] } = useKbList();
  const trainableKbList = useMemo(() => kbList.filter((kb) => kb.can_train === true), [kbList]);
  const canTrainAnyKb = trainableKbList.length > 0;
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [trainTab, setTrainTab] = useState<"file" | "text">("file");
  const [selectedTrainKbUuid, setSelectedTrainKbUuid] = useState("");
  const [textTrainValue, setTextTrainValue] = useState("");
  const [selectedTrainFile, setSelectedTrainFile] = useState<File | null>(null);
  const [dragOverTrainFile, setDragOverTrainFile] = useState(false);
  const [contextNotice, setContextNotice] = useState<string | null>(null);
  const [inputDraft, setInputDraft] = useState("");
  const [activeTrainingRunId, setActiveTrainingRunId] = useState<string | undefined>(undefined);
  const [showTrainingProgressModal, setShowTrainingProgressModal] = useState(false);
  const [showTrainingDoneModal, setShowTrainingDoneModal] = useState(false);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const trainFileRef = useRef<HTMLInputElement | null>(null);
  /** Üres kezdőállapot ne írja felül a mentett beszélgetést (layout után engedélyezzük a mentést) */
  const persistEnabledRef = useRef(false);
  /** Utolsó ismert user id – unmount/pagehide mentéshez, ha a store már null */
  const lastUserIdRef = useRef<number | string | null>(null);
  const messagesRef = useRef<ChatMessageType[]>(messages);
  const contextNoticeRef = useRef<string | null>(contextNotice);
  const inputDraftRef = useRef(inputDraft);
  messagesRef.current = messages;
  contextNoticeRef.current = contextNotice;
  inputDraftRef.current = inputDraft;
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
  }, [user?.id, messages, contextNotice, inputDraft, flushPersistToDisk]);

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
    if (!trainableKbList.length) {
      setSelectedTrainKbUuid("");
      return;
    }
    if (trainableKbList.some((kb) => kb.uuid === selectedTrainKbUuid)) return;
    setSelectedTrainKbUuid(trainableKbList[0].uuid);
  }, [selectedTrainKbUuid, trainableKbList]);

  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => (isTrainingActive(state.data?.status) ? 1500 : 4000),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const trainingProgress = useMemo(() => getTrainingProgress(activeTrainingRun), [activeTrainingRun]);
  const simTrainingRunning =
    createTextMutation.isPending || createFileMutation.isPending || isTrainingActive(activeTrainingRun?.status);
  const effectiveTrainKbUuid = selectedTrainKbUuid || trainableKbList[0]?.uuid || "";
  const effectiveChatKbUuid = effectiveTrainKbUuid || kbList[0]?.uuid || "";
  const selectedTrainKb = useMemo(
    () => trainableKbList.find((kb) => kb.uuid === effectiveTrainKbUuid) ?? null,
    [effectiveTrainKbUuid, trainableKbList]
  );
  const trainingStatusLabel = useMemo(() => getTrainingStatusLabel(activeTrainingRun), [activeTrainingRun]);
  const trainingStatusDetail = useMemo(() => getTrainingStatusDetail(activeTrainingRun), [activeTrainingRun]);

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
    if (!activeTrainingRunId || !activeTrainingRun) return;
    if (isTrainingActive(activeTrainingRun.status)) {
      setShowTrainingProgressModal(true);
      return;
    }

    setShowTrainingProgressModal(false);
    if (activeTrainingRun.status === "completed") {
      const u = useAuthStore.getState().user;
      if (u && u.tenant_kb_has_training !== true) {
        setUser({ ...u, tenant_kb_has_training: true });
      }
      setShowTrainingDoneModal(true);
    } else {
      toast.error(getTrainingFailureMessage(activeTrainingRun) ?? "A tanítás futása sikertelen.");
    }

    setActiveTrainingRunId(undefined);
    requestAnimationFrame(() => flushPersistToDisk());
  }, [activeTrainingRun, activeTrainingRunId, flushPersistToDisk, setUser]);

  const appendMessage = useCallback((msg: ChatMessageType) => {
    setMessages((prev) => {
      const next = trimToLastN([...prev, msg], MAX_CHAT_MESSAGES);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setContextNotice(null);
    setInputDraft("");
    try {
      localStorage.removeItem(CHAT_CONTEXT_STORAGE_KEY);
      const id = useAuthStore.getState().user?.id;
      if (id) {
        localStorage.removeItem(chatPersistKey(id));
        sessionStorage.removeItem(chatLegacySessionKey(id));
      }
    } catch {
      // storage optional
    }
  }, []);

  const send = useCallback(async () => {
    const raw = inputDraft.trim();
    if (!raw || loading) return;

    const question = sanitizeMessage(raw);
    setInputDraft("");

    if (isClearHistoryCommand(question)) {
      clearHistory();
      appendMessage({ role: "assistant", text: "Az előzményeket töröltem." });
      requestAnimationFrame(() => flushPersistToDisk());
      return;
    }

    const conversationHistory = buildConversationHistory(messagesRef.current);
    appendMessage({ role: "user", text: question });
    setTimeout(() => inputRef.current?.focus(), 50);
    setLoading(true);
    try {
      const payload: ChatApiRequest = { question, conversation_history: conversationHistory };
      if (effectiveChatKbUuid) payload.kb_uuid = effectiveChatKbUuid;
      const res = await api.post<ChatApiResponse>("/chat", payload);
      const data = res.data;
      const answer = String(data?.answer || "").trim() || "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján.";
      appendMessage({
        role: "assistant",
        text: answer,
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
        sources: Array.isArray(data?.sources) ? data.sources : [],
        debug: data?.debug ?? null,
      });
    } catch (err) {
      appendMessage({
        role: "assistant",
        text: getApiErrorMessage(err) ?? "Nem sikerült választ kapni a chat szolgáltatástól.",
      });
    } finally {
      setLoading(false);
      requestAnimationFrame(() => flushPersistToDisk());
    }
  }, [appendMessage, clearHistory, loading, inputDraft, flushPersistToDisk, effectiveChatKbUuid]);

  const onUploadTraining = () => {
    if (simTrainingRunning || !canTrainAnyKb) return;
    const hasDraftText = inputDraft.trim().length > 0;
    setTrainTab(hasDraftText ? "text" : "file");
    setSelectedTrainFile(null);
    setTextTrainValue(inputDraft);
    if (!effectiveTrainKbUuid && trainableKbList[0]) {
      setSelectedTrainKbUuid(trainableKbList[0].uuid);
    }
    setShowTrainModal(true);
  };

  const onSelectTrainingFile = (file: File | null) => {
    if (!file || simTrainingRunning) return;
    if (!effectiveTrainKbUuid) {
      toast.error("Válassz tudástárat a tanításhoz.");
      return;
    }
    setShowTrainingDoneModal(false);
    createFileMutation.mutate(
      { kbUuid: effectiveTrainKbUuid, files: [file] },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          setShowTrainingProgressModal(true);
          setSelectedTrainFile(null);
          setShowTrainModal(false);
          if (trainFileRef.current) trainFileRef.current.value = "";
          toast.success(`A fájlos tanítás elindult${selectedTrainKb ? `: ${selectedTrainKb.name}` : "."}`);
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error) ?? "A fájlos tanítás indítása sikertelen.");
        },
      }
    );
    if (trainFileRef.current) trainFileRef.current.value = "";
  };

  const onSubmitTextTraining = () => {
    const value = textTrainValue;
    if (!value.trim() || simTrainingRunning) return;
    if (!effectiveTrainKbUuid) {
      toast.error("Válassz tudástárat a tanításhoz.");
      return;
    }
    setShowTrainingDoneModal(false);
    createTextMutation.mutate(
      {
        kbUuid: effectiveTrainKbUuid,
        title: "Chatből tanított szöveg",
        text: value,
      },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          setShowTrainingProgressModal(true);
          setTextTrainValue("");
          setShowTrainModal(false);
          toast.success(`A szöveges tanítás elindult${selectedTrainKb ? `: ${selectedTrainKb.name}` : "."}`);
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error) ?? "A szöveges tanítás indítása sikertelen.");
        },
      }
    );
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <div className="min-w-0 flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-hidden px-4 pt-2 pb-2">
            <div
              ref={messageScrollRef}
              className="relative h-full min-h-0 overflow-y-auto px-2 pt-2 pb-2"
            >
              {contextNotice ? (
                <div className="flex items-start px-2 mb-[1px]">
                  <div className="flex w-full justify-start">
                    <ChatMessage role="assistant" text={contextNotice} />
                  </div>
                </div>
              ) : null}
              {messages.length > 0 ? (
                <div className="space-y-1">
                  {messages.map((msg, index) => (
                    <div key={`${msg.role}-${index}`} className="flex items-start px-2 mb-[1px]">
                      <div className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
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
                          sources={msg.sources}
                          debug={msg.debug}
                        />
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              ) : null}

              <div className="absolute inset-0 flex flex-col items-center justify-center text-[var(--color-muted)] text-sm gap-3 pointer-events-none">
                <div>Kérdezz valamit, és válaszolok abból, amit tanítottál nekem.</div>
                {messages.length > 0 ? (
                  <button
                    type="button"
                    onClick={clearHistory}
                    className="pointer-events-auto text-xs px-2.5 py-1 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-border)]/20"
                  >
                    Előzmény törlése
                  </button>
                ) : null}
              </div>

              {loading && (
                <div className="flex justify-start pt-2 pb-2">
                  <div className="bg-gray-100 text-gray-600 px-4 py-2 rounded-2xl rounded-bl-none animate-pulse border border-gray-200">
                    ...
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input sor: chat mező + Küldés */}
          <input
            ref={trainFileRef}
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="hidden"
            onChange={(e) => setSelectedTrainFile(e.target.files?.[0] ?? null)}
          />
          <div className="shrink-0 w-full bg-[var(--color-background)] px-4 py-3 flex gap-2">
            <div className="relative flex-1 min-w-0 h-[63px]">
              <textarea
                ref={inputRef}
                value={inputDraft}
                onChange={(e) => setInputDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                className={`chat-question-input w-full h-full min-h-0 bg-[var(--color-background)] text-[var(--color-foreground)] border-[1px] border-[var(--color-border)] rounded-lg resize-none box-border text-base leading-relaxed px-3 py-2 ${
                  canTrainAnyKb
                    ? simTrainingRunning
                      ? "pb-6 pr-[7.25rem]"
                      : "pb-6 pr-14"
                    : ""
                }`}
                placeholder="Írd be a kérdésed és nyomj Entert..."
                disabled={loading}
              />
              {canTrainAnyKb ? (
                <div
                  className="absolute bottom-1 right-2 flex items-center gap-1 pointer-events-auto text-sm font-medium text-gray-600 dark:text-gray-400"
                  aria-live={simTrainingRunning ? "polite" : undefined}
                >
                  <button
                    type="button"
                    onClick={onUploadTraining}
                    disabled={simTrainingRunning}
                    className="flex items-center gap-0.5 hover:text-gray-800 dark:hover:text-gray-300 disabled:opacity-100 disabled:cursor-not-allowed disabled:hover:text-gray-600 dark:disabled:hover:text-gray-400"
                    aria-label={t("nav.train")}
                  >
                    <svg
                      className="w-4 h-4 shrink-0 opacity-90"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden
                    >
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                    <span>{t("nav.train")}</span>
                  </button>
                  {simTrainingRunning ? (
                    <span className="flex items-center gap-0.5 shrink-0 text-gray-600 dark:text-gray-400">
                      <svg
                        className="w-3.5 h-3.5 shrink-0 opacity-90"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                      >
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 2" />
                      </svg>
                      <span className="tabular-nums font-medium">
                        {trainingStatusLabel ? `${trainingStatusLabel} ` : ""}
                        {trainingProgress}%
                      </span>
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="flex h-[63px] w-40 shrink-0 items-center">
              <button
                onClick={send}
                disabled={loading}
                className={`w-full h-12 rounded-lg font-semibold transition-all inline-flex items-center justify-center leading-none ${
                  loading
                    ? "bg-[var(--color-border)] text-[var(--color-muted)] cursor-not-allowed"
                    : "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
                }`}
              >
                {loading ? "..." : "Küldés"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {showTrainModal && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-lg rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-4">
            <div className="mb-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTrainTab("file")}
                className={`h-10 px-3 rounded text-sm border ${
                  trainTab === "file"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)]"
                    : "border-[var(--color-border)]"
                }`}
              >
                Fájl feltöltés
              </button>
              <button
                type="button"
                onClick={() => setTrainTab("text")}
                className={`h-10 px-3 rounded text-sm border ${
                  trainTab === "text"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)]"
                    : "border-[var(--color-border)]"
                }`}
              >
                Szöveges tanítás
              </button>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium">Tudástár</label>
              <select
                value={effectiveTrainKbUuid}
                onChange={(e) => setSelectedTrainKbUuid(e.target.value)}
                className="block w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] p-3"
                disabled={simTrainingRunning}
              >
                {trainableKbList.map((kb) => (
                  <option key={kb.uuid} value={kb.uuid}>
                    {kb.name}
                  </option>
                ))}
              </select>
            </div>
            {trainTab === "file" ? (
              <div
                className={`w-full min-h-[160px] rounded-lg border-2 border-dashed p-4 flex flex-col items-center justify-center gap-3 ${
                  dragOverTrainFile ? "border-[var(--color-primary)]" : "border-[var(--color-border)]"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(false);
                  setSelectedTrainFile(e.dataTransfer?.files?.[0] ?? null);
                }}
              >
                <div className="text-sm text-[var(--color-muted)] text-center">
                  Húzd ide a fájlt vagy válassz a gombbal.
                </div>
                {selectedTrainFile ? (
                  <div className="text-xs text-[var(--color-muted)]">{selectedTrainFile.name}</div>
                ) : null}
                <button
                  type="button"
                  onClick={() => trainFileRef.current?.click()}
                  className="text-xs px-2.5 py-1 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-border)]/20 disabled:opacity-50"
                >
                  Fájl feltöltése
                </button>
              </div>
            ) : (
              <textarea
                value={textTrainValue}
                onChange={(e) => setTextTrainValue(e.target.value)}
                className="chat-question-input w-full min-h-[160px] border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-background)]"
                placeholder="Írj be mondatokat vagy bekezdéseket..."
              />
            )}
            {trainTab === "file" ? (
              <div className="mt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-4 py-2 rounded border border-[var(--color-border)]"
                >
                  Vissza
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onSelectTrainingFile(selectedTrainFile);
                  }}
                  disabled={!selectedTrainFile || !effectiveTrainKbUuid || simTrainingRunning}
                  className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] disabled:opacity-50"
                >
                  Tanítás
                </button>
              </div>
            ) : (
              <div className="mt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-4 py-2 rounded border border-[var(--color-border)]"
                >
                  Vissza
                </button>
                <button
                  type="button"
                  onClick={onSubmitTextTraining}
                  disabled={!textTrainValue.trim() || !effectiveTrainKbUuid || simTrainingRunning}
                  className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] disabled:opacity-50"
                >
                  Tanítás
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showTrainingProgressModal ? (
        <div className="fixed inset-0 z-[75] bg-black/40 backdrop-blur-[1px] flex items-center justify-center px-4">
          <div className="w-full max-w-xs rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-6 text-center">
            <div className="relative mx-auto h-24 w-24">
              <div className="absolute inset-0 rounded-full border-4 border-[var(--color-border)]" />
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[var(--color-primary)] animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center text-lg font-bold">{trainingProgress}%</div>
            </div>
            <div className="mt-4 text-sm font-medium">Tanítás folyamatban</div>
            {trainingStatusDetail ? <div className="mt-1 text-xs text-[var(--color-muted)]">{trainingStatusDetail}</div> : null}
            <div className="mt-3 h-1.5 w-full rounded-full bg-[var(--color-border)] overflow-hidden">
              <div
                className="h-full bg-[var(--color-primary)] transition-all duration-150"
                style={{ width: `${trainingProgress}%` }}
              />
            </div>
          </div>
        </div>
      ) : null}

      {showTrainingDoneModal && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-sm rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-5 text-center">
            <div className="text-base font-semibold text-[var(--color-foreground)]">
              A tanítás befejeződött.
            </div>
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => setShowTrainingDoneModal(false)}
                className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)]"
              >
                Bezárás
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
