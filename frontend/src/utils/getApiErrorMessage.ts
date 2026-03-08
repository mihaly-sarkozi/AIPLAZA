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
  if (detail != null && typeof detail === "object" && "message" in detail) {
    const msg = (detail as { message?: unknown }).message;
    return msg != null ? String(msg) : null;
  }
  return null;
}
