import { memo } from "react";
import { sanitizeMessage } from "../../../utils/sanitize";

export type ChatMessageProps = {
  role: string;
  text: string;
  sources?: Array<{
    kb_uuid: string;
    point_id: string;
    title?: string;
    snippet?: string;
    source_url?: string;
  }>;
};

function ChatMessageInner({ role, text, sources = [] }: ChatMessageProps) {
  const isUser = role === "user";
  const sourceHref = (s: { kb_uuid: string; point_id: string; source_url?: string }) => {
    if (s.kb_uuid && s.point_id) {
      return `/chat/source/${encodeURIComponent(s.kb_uuid)}/${encodeURIComponent(s.point_id)}`;
    }
    return s.source_url || "#";
  };
  return (
    <div
      className={`inline-block px-4 py-[6px] rounded-2xl max-w-md shadow-sm whitespace-pre-wrap break-words ${
        isUser
          ? "bg-black text-white rounded-br-none"
          : "bg-gray-100 text-black border border-gray-200 rounded-bl-none"
      }`}
    >
      <div>{sanitizeMessage(text)}</div>
      {!isUser && sources.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-300 text-xs">
          <div className="font-semibold mb-1">Források:</div>
          <div className="space-y-1">
            {sources.map((s, idx) => (
              <div key={`${s.kb_uuid}-${s.point_id}-${idx}`} className="leading-snug">
                <a
                  href={sourceHref(s)}
                  className="underline text-blue-700 hover:text-blue-900"
                >
                  {sanitizeMessage(s.title || `${s.kb_uuid}/${s.point_id}`)}
                </a>
                {s.snippet ? (
                  <div className="text-gray-700 mt-0.5">{sanitizeMessage(s.snippet)}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(ChatMessageInner);
