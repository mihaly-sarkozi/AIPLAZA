import { memo } from "react";
import { sanitizeMessage } from "../utils/sanitize";

export type ChatMessageProps = {
  role: string;
  text: string;
};

function ChatMessageInner({ role, text }: ChatMessageProps) {
  const isUser = role === "user";
  return (
    <div
      className={`inline-block px-4 py-2 rounded-2xl max-w-lg shadow-sm whitespace-pre-wrap break-words ${
        isUser
          ? "bg-black text-white rounded-br-none"
          : "bg-gray-100 text-black border border-gray-200 rounded-bl-none"
      }`}
    >
      {sanitizeMessage(text)}
    </div>
  );
}

export default memo(ChatMessageInner);
