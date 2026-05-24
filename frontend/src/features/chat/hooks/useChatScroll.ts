import { useEffect, useRef } from "react";

export function useChatScroll(dependency: unknown) {
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [dependency]);

  return { messageScrollRef, messagesEndRef };
}
