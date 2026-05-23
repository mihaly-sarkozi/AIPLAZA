/**
 * Parse API error response into a user-facing message.
 * Handles err.response.data.detail as string or { message?: string }.
 */
export function getApiErrorMessage(err: unknown): string | null {
  if (err == null || typeof err !== "object" || !("response" in err)) {
    return null;
  }
  const response = (err as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail != null && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { message?: unknown; debug_message?: unknown };
    const msg = d.message != null ? String(d.message) : null;
    const dbg = d.debug_message != null ? String(d.debug_message) : null;
    if (msg && dbg) return `${msg} (${dbg})`;
    if (msg) return msg;
    if (dbg) return dbg;
  }
  return null;
}
