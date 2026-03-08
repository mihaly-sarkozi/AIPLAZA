/**
 * Chat WebSocket URL builder. Token must be passed as query param for auth.
 */
export function getChatWsUrl(token: string | null): string {
  if (!token) return "";
  const base = import.meta.env.VITE_API_URL ?? "/api";
  let wsBase: string;
  if (typeof base === "string" && base.startsWith("http://")) {
    wsBase = base.replace("http://", "ws://");
  } else if (typeof base === "string" && base.startsWith("https://")) {
    wsBase = base.replace("https://", "wss://");
  } else {
    const protocol = typeof window !== "undefined" && window.location?.protocol === "https:" ? "wss:" : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "";
    const path = typeof base === "string" && base.startsWith("/") ? base : "/api";
    wsBase = `${protocol}//${host}${path}`;
  }
  const basePath = wsBase.replace(/\/+$/, "");
  const url = `${basePath}/chat/ws`;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(token)}`;
}
