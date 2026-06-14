/**
 * Parse API error response into a user-facing message.
 * Handles err.response.data.detail as string or { code?, params?, message? }.
 */
import { t } from "../i18n";

const API_ERROR_I18N_KEYS: Record<string, string> = {
  text_required: "kb.errorTextRequired",
  text_too_long: "kb.errorTextTooLong",
  batch_not_found: "kb.errorBatchNotFound",
  duplicate_content: "kb.errorDuplicateContent",
  validation_error: "kb.errorValidation",
  storage_raw_ref_mismatch: "kb.errorStorageRawRefMismatch",
  storage_error: "kb.errorStorage",
  queue_unavailable: "kb.errorQueueUnavailable",
  kb_not_found: "kb.errorNotFound",
  knowledge_base_not_found: "kb.errorNotFound",
  kb_name_exists: "kb.errorNameExists",
  kb_name_invalid: "kb.errorNameInvalid",
  kb_confirm_name_mismatch: "kb.errorConfirmNameMismatch",
  kb_limit_reached: "kb.errorLimitReached",
  kb_delete_not_allowed: "kb.errorDeleteNotAllowed",
};

function applyParams(template: string, params: Record<string, unknown>): string {
  return Object.entries(params).reduce(
    (message, [key, value]) => message.replace(`{{${key}}}`, String(value)),
    template
  );
}

function messageFromCode(code: string, params?: Record<string, unknown>): string | null {
  const i18nKey = API_ERROR_I18N_KEYS[code];
  if (!i18nKey) return null;
  const template = t(i18nKey);
  if (params && Object.keys(params).length > 0) {
    return applyParams(template, params);
  }
  return template;
}

function readApiErrorDetail(err: unknown): {
  status?: number;
  detail?: unknown;
} | null {
  if (err == null || typeof err !== "object" || !("response" in err)) {
    return null;
  }
  const response = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response;
  if (!response) return null;
  return { status: response.status, detail: response.data?.detail };
}

/** API hiba `detail.code` mezője (pl. `duplicate_content`). */
export function getApiErrorCode(err: unknown): string | null {
  const parsed = readApiErrorDetail(err);
  const detail = parsed?.detail;
  if (detail != null && typeof detail === "object" && !Array.isArray(detail)) {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === "string" && code.trim()) return code.trim();
  }
  return null;
}

/** Szöveges tanítás: ugyanaz a tartalom már szerepel a tudástárban (HTTP 409). */
export function isDuplicateContentError(err: unknown): boolean {
  const parsed = readApiErrorDetail(err);
  if (parsed?.status === 409 && getApiErrorCode(err) === "duplicate_content") return true;
  return getApiErrorCode(err) === "duplicate_content";
}

export function getApiErrorMessage(err: unknown): string | null {
  const parsed = readApiErrorDetail(err);
  const detail = parsed?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail != null && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as {
      code?: unknown;
      params?: unknown;
      message?: unknown;
      debug_message?: unknown;
    };
    if (typeof d.code === "string") {
      const params =
        d.params != null && typeof d.params === "object" && !Array.isArray(d.params)
          ? (d.params as Record<string, unknown>)
          : undefined;
      const translated = messageFromCode(d.code, params);
      if (translated) return translated;
    }
    const msg = d.message != null ? String(d.message) : null;
    const dbg = d.debug_message != null ? String(d.debug_message) : null;
    if (msg && dbg) return `${msg} (${dbg})`;
    if (msg) return msg;
    if (dbg) return dbg;
    if (typeof d.code === "string") return d.code;
  }
  return null;
}
