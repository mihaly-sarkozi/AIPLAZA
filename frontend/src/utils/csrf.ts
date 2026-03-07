/**
 * CSRF token in memory only (not in localStorage/sessionStorage).
 * Fetched on app init; attached to POST/PATCH/PUT/DELETE by axios interceptor.
 */

let csrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return csrfToken;
}

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}
