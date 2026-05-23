import api from "../../../api/axiosClient";

/**
 * Beállítja a ws_token HttpOnly cookie-t (GET /chat/ws-token). Hívd meg WebSocket nyitása előtt.
 * A kérés Bearer tokennel megy (axios interceptor); a válasz Set-Cookie: ws_token=...
 */
export async function ensureChatWsToken(): Promise<void> {
  await api.get("/chat/ws-token");
}

/**
 * Chat WebSocket base URL. Auth: HttpOnly cookie (ws_token), nem query param (biztonság: ne kerüljön logokba).
 * A kapcsolat előtt hívd ensureChatWsToken()-t (GET /chat/ws-token), hogy a backend beállítsa a cookie-t.
 */
export function getChatWsUrl(): string {
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
  return `${basePath}/chat/ws`;
}
