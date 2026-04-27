import { memo, useState } from "react";
import { sanitizeMessage } from "../../../utils/sanitize";
import api from "../../../api/axiosClient";
import { toast } from "sonner";

type EvidenceItem = {
  claim_id?: string;
  sentence_id?: string;
  source_id?: string;
  claim_text?: string;
  sentence_text?: string;
  [key: string]: unknown;
};

export type ChatMessageProps = {
  role: string;
  text: string;
  question?: string;
  queryRunId?: string | null;
  answerMode?: string;
  answerSource?: string;
  confidence?: number;
  evidence?: EvidenceItem[];
  citedClaimIds?: string[];
  citedSentenceIds?: string[];
  citedSourceIds?: string[];
  queryProfile?: Record<string, unknown>;
  matchedChunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  debug?: Record<string, unknown> | null;
  sources?: Array<{
    kb_uuid: string;
    point_id: string;
    source_id?: string;
    title?: string;
    snippet?: string;
    source_url?: string;
    source_type?: string;
    file_ref?: string | null;
    display_type?: string;
    created_by?: number | null;
    created_by_label?: string;
  }>;
};

function formatPercent(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "0%";
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function shortLabel(value: string, maxLength = 42): string {
  const text = value.trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function sourceDisplayName(source: NonNullable<ChatMessageProps["sources"]>[number]): string {
  return source.file_ref || source.title || source.source_id || source.point_id || "Forrás";
}

function sourceMode(source: NonNullable<ChatMessageProps["sources"]>[number] | undefined): string {
  if (!source) return "";
  if (source.display_type) return source.display_type;
  const name = String(source.file_ref || source.title || "").toLowerCase();
  if (name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".docx")) return "DOCX";
  if (name.endsWith(".doc")) return "DOC";
  if (source.source_type === "text") return "Gépelés";
  if (source.source_type === "url") return "URL";
  return source.source_type === "file" ? "Fájl" : "";
}

function filenameFromContentDisposition(value: string | undefined): string | null {
  if (!value) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encoded?.[1]) return decodeURIComponent(encoded[1]);
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain?.[1] ?? null;
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function ChatMessageInner({
  role,
  text,
  question,
  queryRunId,
  answerMode,
  answerSource,
  confidence,
  evidence = [],
  citedClaimIds = [],
  citedSentenceIds = [],
  citedSourceIds = [],
  queryProfile,
  matchedChunks = [],
  claims = [],
  debug,
  sources = [],
}: ChatMessageProps) {
  const isUser = role === "user";
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null);
  const [sourceLoadingId, setSourceLoadingId] = useState<string | null>(null);
  const hasKnowledgeDetails = !isUser && (answerMode || evidence.length > 0 || typeof confidence === "number");
  const primarySource = sources[0];
  const displayMode = sourceMode(primarySource);
  const displayRecorder = primarySource?.created_by_label || (primarySource?.created_by ? `Felhasználó #${primarySource.created_by}` : "");
  const submitFeedback = async (value: "like" | "dislike") => {
    setFeedback(value);
    if (!queryRunId) return;
    try {
      await api.post("/chat/feedback", {
        trace_id: queryRunId,
        helpful: value === "like",
      });
    } catch {
      toast.error("A visszajelzés mentése nem sikerült.");
    }
  };
  const downloadSource = async (sourceId: string | undefined) => {
    if (!sourceId) {
      toast.error("Ehhez a hivatkozáshoz nincs letölthető forrás azonosító.");
      return;
    }
    setSourceLoadingId(sourceId);
    try {
      const url = queryRunId
        ? `/chat/sources/${encodeURIComponent(queryRunId)}/${encodeURIComponent(sourceId)}/download`
        : `/knowledge/sources/${encodeURIComponent(sourceId)}/download`;
      const res = await api.get(url, {
        responseType: "blob",
      });
      const filename =
        filenameFromContentDisposition(res.headers["content-disposition"]) ||
        sourceDisplayName(sources.find((item) => (item.source_id || item.point_id) === sourceId) || primarySource || { point_id: sourceId, kb_uuid: "" });
      downloadBlob(filename, res.data);
    } catch {
      toast.error("A forrás tartalmát nem sikerült letölteni.");
    } finally {
      setSourceLoadingId(null);
    }
  };
  const downloadTrace = () => {
    downloadJson(`aiplaza-answer-trace-${queryRunId || Date.now()}.json`, {
      validation_purpose: "AI answer validation package",
      question,
      answer: text,
      query_run_id: queryRunId,
      answer_mode: answerMode,
      answer_source: answerSource,
      confidence,
      evidence,
      cited_claim_ids: citedClaimIds,
      cited_sentence_ids: citedSentenceIds,
      cited_source_ids: citedSourceIds,
      source_references: sources,
      query_interpretation: queryProfile ?? debug?.query_profile ?? debug?.query_focus ?? {},
      knowledge_interpretation: {
        matched_chunks: matchedChunks.length ? matchedChunks : debug?.matched_chunks ?? [],
        claims: claims.length ? claims : debug?.claims ?? [],
        scoring_summary: debug?.scoring_summary ?? {},
        context_preview: debug?.context_preview ?? "",
      },
      raw_debug: debug ?? {},
    });
  };
  return (
    <div
      className={`inline-block px-4 py-[6px] rounded-2xl max-w-md shadow-sm whitespace-pre-wrap break-words ${
        isUser
          ? "bg-black text-white rounded-br-none text-sm leading-snug"
          : "bg-gray-100 text-black border border-gray-200 rounded-bl-none"
      }`}
    >
      {hasKnowledgeDetails ? (
        <div className="space-y-2">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Válasz</div>
            <div>{sanitizeMessage(text)}</div>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px] text-gray-600">
            <span className="rounded bg-white/70 px-2 py-0.5">Bizonyosság: {formatPercent(confidence)}</span>
            {displayMode ? <span className="rounded bg-white/70 px-2 py-0.5">Mód: {sanitizeMessage(displayMode)}</span> : null}
            {displayRecorder ? <span className="rounded bg-white/70 px-2 py-0.5">Forrás: {sanitizeMessage(displayRecorder)}</span> : null}
          </div>
        </div>
      ) : (
        <div>{sanitizeMessage(text)}</div>
      )}
      {!isUser && sources.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-300 text-xs">
          <div className="font-semibold mb-1">Hivatkozás az eredeti tartalomra:</div>
          <div className="space-y-1">
            {sources.map((s, idx) => (
              <div key={`${s.kb_uuid}-${s.point_id}-${idx}`} className="leading-snug">
                <button
                  type="button"
                  onClick={() => downloadSource(s.source_id)}
                  disabled={!s.source_id || sourceLoadingId === s.source_id}
                  className="underline text-left text-blue-700 hover:text-blue-900 disabled:opacity-60"
                >
                  {sanitizeMessage(shortLabel(sourceDisplayName(s)))}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {!isUser ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-gray-300 pt-2 text-xs">
          <button
            type="button"
            onClick={() => submitFeedback("like")}
            className={`rounded border px-2 py-1 ${feedback === "like" ? "bg-green-100 border-green-300" : "bg-white/70 border-gray-300"}`}
          >
            Like
          </button>
          <button
            type="button"
            onClick={() => submitFeedback("dislike")}
            className={`rounded border px-2 py-1 ${feedback === "dislike" ? "bg-red-100 border-red-300" : "bg-white/70 border-gray-300"}`}
          >
            Dislike
          </button>
          <button
            type="button"
            onClick={downloadTrace}
            className="rounded border border-gray-300 bg-white/70 px-2 py-1 hover:bg-white"
          >
            Trace export
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default memo(ChatMessageInner);
