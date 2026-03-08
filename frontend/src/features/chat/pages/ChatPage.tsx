import { useState, useEffect, useRef, useCallback, useLayoutEffect } from "react";
import { VariableSizeList as List } from "react-window";
import { useAuthStore } from "../../../store/authStore";
import { sanitizeMessage } from "../../../utils/sanitize";
import { getChatWsUrl } from "../api/chatWs";
import ChatMessage from "../components/ChatMessage";

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
    <div style={style} className="flex items-start px-2 pb-1">
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

export default function ChatPage() {
  const token = useAuthStore((s) => s.token);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<List | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const rowHeights = useRef<Record<number, number>>({});
  const [listSize, setListSize] = useState({ width: 400, height: 300 });

  const setRowHeight = useCallback((index: number, height: number) => {
    rowHeights.current[index] = height;
  }, []);

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

  const ensureConnection = useCallback((): WebSocket | null => {
    if (!token) return null;
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current;
    const url = getChatWsUrl(token);
    if (!url) return null;
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
    if (!raw || loading) return;

    const question = sanitizeMessage(raw);
    if (el) el.value = "";

    appendMessage({ role: "user", text: question });
    setLoading(true);
    appendMessage({ role: "assistant", text: "" });

    const ws = ensureConnection();
    if (!ws) {
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant" && next[next.length - 1].text === "") {
          next[next.length - 1] = { role: "assistant", text: "⚠️ Nincs kapcsolat. Jelentkezz be újra." };
        }
        return next;
      });
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
      return;
    }

    const onMessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data as string);
        if (data.chunk !== undefined) {
          appendChunkToLast(data.chunk);
        }
        if (data.done === true) {
          setLoading(false);
          ws.removeEventListener("message", onMessage);
          setTimeout(() => inputRef.current?.focus(), 50);
        }
        if (data.error) {
          appendChunkToLast(`⚠️ ${data.error}`);
          setLoading(false);
          ws.removeEventListener("message", onMessage);
        }
      } catch {
        setLoading(false);
        ws.removeEventListener("message", onMessage);
      }
    };

    const onOpen = () => {
      ws.send(JSON.stringify({ question: raw }));
    };

    const onError = () => {
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant" && next[next.length - 1].text === "") {
          next[next.length - 1] = { role: "assistant", text: "⚠️ Hiba történt a válasz lekérése közben." };
        }
        return next;
      });
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    };

    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ question: raw }));
      ws.addEventListener("message", onMessage);
    } else {
      ws.addEventListener("open", onOpen, { once: true });
      ws.addEventListener("message", onMessage);
      ws.addEventListener("error", onError, { once: true });
      ws.addEventListener("close", () => {
        setLoading(false);
        ws.removeEventListener("message", onMessage);
      }, { once: true });
    }
  }, [loading, appendMessage, appendChunkToLast, ensureConnection]);

  const listData = {
    messages,
    listRef,
    rowHeights,
    setRowHeight,
  };

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

      <div className="shrink-0 w-full bg-[var(--color-background)] border-t border-[var(--color-border)] p-4 flex items-center gap-2">
        <textarea
          ref={inputRef}
          defaultValue=""
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className="flex-1 bg-[var(--color-background)] text-[var(--color-foreground)] border border-[var(--color-border)] p-3 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
          placeholder="Írd be a kérdésed és nyomj Entert..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className={`px-6 py-3 rounded-lg font-semibold transition-all ${
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
