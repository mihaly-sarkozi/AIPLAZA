/**
 * Password validation for change-password and set-password flows.
 * Returns null if valid, otherwise an i18n error code (e.g. profile.passwordMinLength).
 */

export const PASSWORD_ERROR_MIN_LENGTH = "profile.passwordMinLength";
export const PASSWORD_ERROR_REQUIRES_LOWER = "profile.passwordRequiresLower";
export const PASSWORD_ERROR_REQUIRES_UPPER = "profile.passwordRequiresUpper";
export const PASSWORD_ERROR_REQUIRES_NUMBER = "profile.passwordRequiresNumber";

const MIN_LENGTH = 6;

export function validatePassword(password: string): string | null {
  if (password.length < MIN_LENGTH) {
    return PASSWORD_ERROR_MIN_LENGTH;
  }
  if (!/[a-z]/.test(password)) {
    return PASSWORD_ERROR_REQUIRES_LOWER;
  }
  if (!/[A-Z]/.test(password)) {
    return PASSWORD_ERROR_REQUIRES_UPPER;
  }
  if (!/\d/.test(password)) {
    return PASSWORD_ERROR_REQUIRES_NUMBER;
  }
  return null;
}
