import { useState, useEffect, useRef, useCallback, useLayoutEffect } from "react";
import { useNavigate } from "react-router-dom";
import { VariableSizeList as List } from "react-window";
import { useAuthStore } from "../../../store/authStore";
import { sanitizeMessage } from "../../../utils/sanitize";
import { ensureChatWsToken, getChatWsUrl } from "../api/chatWs";
import ChatMessage from "../components/ChatMessage";
import { toast } from "sonner";
import { useKbList } from "../../knowledge-base/hooks/useKb";
import { useTranslation } from "../../../i18n";

const MAX_CHAT_MESSAGES = 100;
const ESTIMATED_ROW_HEIGHT = 72;

export type ChatMessageType = { role: string; text: string };

function trimToLastN(messages: ChatMessageType[], n: number): ChatMessageType[] {
  if (messages.length <= n) return messages;
  return messages.slice(-n);
}

interface MessageRowProps {
  index: number;
  style: React.CSSProperties;
  data: {
    messages: ChatMessageType[];
    listRef: React.RefObject<List | null>;
    rowHeights: React.MutableRefObject<Record<number, number>>;
    setRowHeight: (index: number, height: number) => void;
  };
}

function MessageRow({ index, style, data }: MessageRowProps) {
  const { messages, listRef, rowHeights, setRowHeight } = data;
  const rowRef = useRef<HTMLDivElement | null>(null);
  const msg = messages[index];

  useLayoutEffect(() => {
    if (!rowRef.current || !listRef.current) return;
    const height = rowRef.current.getBoundingClientRect().height;
    if (rowHeights.current[index] !== height) {
      setRowHeight(index, height);
      listRef.current.resetAfterIndex(index);
    }
  }, [index, listRef, msg?.text, rowHeights, setRowHeight]);

  if (!msg) return null;

  return (
    <div style={style} className="flex items-start px-2 mb-[1px]">
      <div ref={rowRef} className="w-full min-h-[2rem]">
        <div
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <ChatMessage role={msg.role} text={msg.text} />
        </div>
      </div>
    </div>
  );
}

/** Üres tömb = Mind (minden tudástár); nem üres = csak a kiválasztott uuid-k. */

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<List | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const rowHeights = useRef<Record<number, number>>({});
  const [listSize, setListSize] = useState({ width: 400, height: 300 });
  const { data: kbList = [] } = useKbList();
  const [selectedKbUuids, setSelectedKbUuids] = useState<string[]>([]);
  const [kbDropdownOpen, setKbDropdownOpen] = useState(false);
  const kbDropdownRef = useRef<HTMLDivElement | null>(null);

  const setRowHeight = useCallback((index: number, height: number) => {
    rowHeights.current[index] = height;
  }, []);

  const isAllKbs = selectedKbUuids.length === 0;
  const toggleAllKbs = useCallback(() => {
    setSelectedKbUuids([]);
  }, []);
  const toggleKb = useCallback((uuid: string) => {
    setSelectedKbUuids((prev) =>
      prev.includes(uuid) ? prev.filter((id) => id !== uuid) : [...prev, uuid]
    );
  }, []);

  useEffect(() => {
    if (!kbDropdownOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (kbDropdownRef.current && !kbDropdownRef.current.contains(e.target as Node)) {
        setKbDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [kbDropdownOpen]);

  const getItemSize = useCallback((index: number) => {
    return rowHeights.current[index] ?? ESTIMATED_ROW_HEIGHT;
  }, []);

  const scrollToBottom = useCallback(() => {
    if (listRef.current && messages.length > 0) {
      listRef.current.scrollToItem(messages.length - 1, "end");
    }
  }, [messages.length]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect ?? {};
      if (width != null && height != null) setListSize({ width, height });
    });
    ro.observe(el);
    setListSize({ width: el.clientWidth, height: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const appendMessage = useCallback((msg: ChatMessageType) => {
    setMessages((prev) => {
      const next = trimToLastN([...prev, msg], MAX_CHAT_MESSAGES);
      if (next.length !== prev.length + 1) rowHeights.current = {};
      return next;
    });
  }, []);

  const appendChunkToLast = useCallback((chunk: string) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      if (last.role !== "assistant") return prev;
      const next = [...prev];
      next[next.length - 1] = { ...last, text: last.text + chunk };
      return next;
    });
  }, []);

  const ensureConnection = useCallback(async (): Promise<WebSocket | null> => {
    if (!token) return null;
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current;
    try {
      await ensureChatWsToken();
    } catch {
      return null;
    }
    const url = getChatWsUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;
    return ws;
  }, [token]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const send = useCallback(() => {
    const el = inputRef.current;
    const raw = el?.value?.trim() ?? "";
    if (!raw) return;

    const question = sanitizeMessage(raw);
    if (el) el.value = "";

    appendMessage({ role: "user", text: question });
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [appendMessage]);

  const listData = {
    messages,
    listRef,
    rowHeights,
    setRowHeight,
  };

  const kbButtonLabel =
    isAllKbs
      ? t("chat.allKbs")
      : selectedKbUuids.length === 1
        ? kbList.find((k) => k.uuid === selectedKbUuids[0])?.name ?? selectedKbUuids[0]
        : t("chat.kbCount").replace("{n}", String(selectedKbUuids.length));

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div ref={containerRef} className="flex-1 min-h-0 flex flex-col p-4">
        {messages.length > 0 ? (
          <List
            ref={listRef}
            height={listSize.height}
            width={listSize.width}
            itemCount={messages.length}
            itemSize={getItemSize}
            itemData={listData}
            overscanCount={5}
            className="scrollbar-thin"
          >
            {MessageRow}
          </List>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] text-sm">
            Írd be a kérdésed lent, majd nyomj Entert.
          </div>
        )}

        {loading && (
          <div className="flex justify-start pt-2 pb-2">
            <div className="bg-gray-100 text-gray-600 px-4 py-2 rounded-2xl rounded-bl-none animate-pulse border border-gray-200">
              ...
            </div>
          </div>
        )}
      </div>

      {/* Egy sor: tudástár legördülő + Tanítás gomb alatta | chat mező + Küldés */}
      <div className="shrink-0 w-full bg-[var(--color-background)] border-t border-[var(--color-border)] px-4 py-3 flex items-center gap-2">
        <div className="flex flex-col gap-1.5 shrink-0">
          <div className="relative" ref={kbDropdownRef}>
            <button
              type="button"
              onClick={() => setKbDropdownOpen((o) => !o)}
              className="flex items-center gap-1 px-2 py-1.5 rounded border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)] text-xs hover:bg-[var(--color-border)]/30 w-[20ch] min-w-[20ch] max-w-[20ch]"
            >
              <span className="truncate flex-1 min-w-0 text-left">{kbButtonLabel}</span>
              <svg className="w-3 h-3 shrink-0 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={kbDropdownOpen ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
              </svg>
            </button>
            {kbDropdownOpen && (
              <div className="absolute left-0 bottom-full mb-1 z-20 min-w-[10rem] max-w-[14rem] max-h-56 overflow-y-auto rounded border border-[var(--color-border)] bg-[var(--color-card)] shadow-lg py-0.5">
                <button
                  type="button"
                  onClick={() => { toggleAllKbs(); }}
                  className="w-full flex items-center gap-1.5 px-2 py-1.5 text-left text-xs hover:bg-[var(--color-border)]/30"
                >
                  <span className="w-3.5 h-3.5 flex items-center justify-center border border-[var(--color-border)] rounded bg-[var(--color-background)] shrink-0">
                    {isAllKbs ? "✓" : ""}
                  </span>
                  {t("chat.allKbs")}
                </button>
                {kbList.map((kb) => {
                  const checked = selectedKbUuids.includes(kb.uuid);
                  return (
                    <button
                      key={kb.uuid}
                      type="button"
                      onClick={() => toggleKb(kb.uuid)}
                      className="w-full flex items-center gap-1.5 px-2 py-1.5 text-left text-xs hover:bg-[var(--color-border)]/30"
                    >
                      <span className="w-3.5 h-3.5 flex items-center justify-center border border-[var(--color-border)] rounded bg-[var(--color-background)] shrink-0">
                        {checked ? "✓" : ""}
                      </span>
                      <span className="truncate">{kb.name}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              if (selectedKbUuids.length !== 1) {
                toast.info("A tanításhoz ki kell választani egy tudástárat.");
                return;
              }
              const selected = kbList.find((k) => k.uuid === selectedKbUuids[0]);
              if (!selected?.can_train) {
                toast.info("Ehhez a tudástárhoz nincs tanítási jogosultságod.");
                return;
              }
              navigate(`/kb/train/${selectedKbUuids[0]}`);
            }}
            className={`flex items-center justify-center px-2 py-1.5 rounded text-xs ${
              selectedKbUuids.length === 1 && kbList.find((k) => k.uuid === selectedKbUuids[0])?.can_train === true
                ? "bg-black text-white hover:opacity-90"
                : "bg-gray-300 text-gray-600 dark:bg-gray-600 dark:text-gray-400 cursor-not-allowed"
            }`}
          >
            <span>Tanítás</span>
          </button>
        </div>
        <textarea
          ref={inputRef}
          defaultValue=""
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className="flex-1 min-w-0 bg-[var(--color-background)] text-[var(--color-foreground)] border border-[var(--color-border)] px-3 py-2 rounded-lg resize-none h-[66px] min-h-[66px] box-border text-sm focus:outline-none focus:border-gray-500 dark:focus:border-gray-400"
          placeholder="Írd be a kérdésed és nyomj Entert..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className={`shrink-0 px-6 py-3 rounded-lg font-semibold transition-all ${
            loading
              ? "bg-[var(--color-border)] text-[var(--color-muted)] cursor-not-allowed"
              : "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
          }`}
        >
          {loading ? "..." : "Küldés"}
        </button>
      </div>
    </div>
  );
}
