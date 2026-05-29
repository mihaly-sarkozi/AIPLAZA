/**
 * CSRF token in memory only (not in localStorage/sessionStorage).
 * Fetched on app init; attached to POST/PATCH/PUT/DELETE by axios interceptor.
 */

let tenantCsrfToken: string | null = null;
let platformAdminCsrfToken: string | null = null;

export type CsrfScope = "tenant" | "platform-admin";

export function getCsrfToken(scope: CsrfScope = "tenant"): string | null {
  return scope === "platform-admin" ? platformAdminCsrfToken : tenantCsrfToken;
}

export function setCsrfToken(token: string | null, scope: CsrfScope = "tenant"): void {
  if (scope === "platform-admin") {
    platformAdminCsrfToken = token;
    return;
  }
  tenantCsrfToken = token;
}
