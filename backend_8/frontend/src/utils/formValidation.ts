/**
 * Reusable form validation helpers. Return an i18n key (string) on error, null when valid.
 * Use with t(key) in the form to display the message.
 */

export const VALIDATION_ERROR_REQUIRED = "common.fieldRequired";
export const VALIDATION_ERROR_EMAIL = "common.invalidEmail";

/** Returns i18n error key if value is empty/whitespace, null if valid. */
export function validateRequired(value: string): string | null {
  if (value == null || String(value).trim() === "") return VALIDATION_ERROR_REQUIRED;
  return null;
}

/** Returns i18n error key if value is not a valid email, null if valid. */
export function validateEmail(value: string): string | null {
  const trimmed = value == null ? "" : String(value).trim();
  if (trimmed === "") return VALIDATION_ERROR_REQUIRED;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) return VALIDATION_ERROR_EMAIL;
  return null;
}

export {
  validatePassword,
  PASSWORD_ERROR_MIN_LENGTH,
  PASSWORD_ERROR_REQUIRES_LOWER,
  PASSWORD_ERROR_REQUIRES_UPPER,
  PASSWORD_ERROR_REQUIRES_NUMBER,
} from "./passwordValidation";
