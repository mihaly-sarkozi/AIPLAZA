import { memo, useState } from "react";
import { sanitizeMessage } from "../../../utils/sanitize";
import api from "../../../api/axiosClient";
import { toast } from "sonner";

export type ChatMessageProps = {
  role: string;
  text: string;
  question?: string;
  queryRunId?: string | null;
  answerMode?: string;
  answerSource?: string;
  confidence?: number;
  evidence?: Array<Record<string, unknown>>;
  citedClaimIds?: string[];
  citedSentenceIds?: string[];
  citedSourceIds?: string[];
  queryProfile?: Record<string, unknown>;
  matchedChunks?: Array<Record<string, unknown>>;
  claims?: Array<Record<string, unknown>>;
  contextBlocks?: Array<Record<string, unknown>>;
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

function shortLabel(value: string, maxLength = 42): string {
  const text = value.trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function sourceDisplayName(source: NonNullable<ChatMessageProps["sources"]>[number]): string {
  return source.file_ref || source.title || source.source_id || source.point_id || "Forrás";
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
  queryRunId,
  sources = [],
}: ChatMessageProps) {
  const isUser = role === "user";
  const [sourceLoadingId, setSourceLoadingId] = useState<string | null>(null);
  const primarySource = sources[0];
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
  return (
    <div
      className={`inline-block px-4 py-[6px] rounded-2xl max-w-md shadow-sm whitespace-pre-wrap break-words ${
        isUser
          ? "bg-black text-white rounded-br-none text-sm leading-snug"
          : "bg-gray-100 text-black border border-gray-200 rounded-bl-none"
      }`}
    >
      <div>{sanitizeMessage(text)}</div>
      {!isUser && sources.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-300 text-xs">
          <div className="font-semibold mb-1">Forrás:</div>
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
    </div>
  );
}

export default memo(ChatMessageInner);
