/**
 * Host alapú domain típus: főoldal (landing) vs tenant aldomain.
 * VITE_TENANT_DOMAIN = backend tenant_base_domain (pl. app.test).
 */

const TENANT_BASE_DOMAIN = import.meta.env.VITE_TENANT_DOMAIN ?? "app.test";

export function getTenantBaseDomain(): string {
  return TENANT_BASE_DOMAIN;
}

/** Főoldal (landing) domain: app.test, www.app.test, localhost, 127.0.0.1 */
export function isMainDomain(): boolean {
  const host = typeof window !== "undefined" ? window.location.hostname : "";
  if (host === "localhost" || host === "127.0.0.1") return true;
  if (host === TENANT_BASE_DOMAIN) return true;
  if (host === `www.${TENANT_BASE_DOMAIN}`) return true;
  return false;
}

/** Tenant aldomain: pl. acme.app.test (nem app.test) */
export function isTenantSubdomain(): boolean {
  const host = typeof window !== "undefined" ? window.location.hostname : "";
  if (!host || host === "localhost" || host === "127.0.0.1") return false;
  if (host === TENANT_BASE_DOMAIN || host === `www.${TENANT_BASE_DOMAIN}`) return false;
  return host.endsWith(`.${TENANT_BASE_DOMAIN}`);
}
