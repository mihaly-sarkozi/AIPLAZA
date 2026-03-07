/**
 * Strict validation for login redirect query parameter.
 * Only allows internal routes: /chat, /kb, /admin/*, /settings.
 * Rejects protocol, hostname, encoded external URLs, and any path not in the allowlist.
 */

const DEFAULT_REDIRECT = "/chat";

/** Allowed path prefixes (exact or prefix match). Order: more specific first if needed. */
const ALLOWED: Array<{ exact?: string; prefix?: string }> = [
  { exact: "/chat" },
  { exact: "/kb" },
  { prefix: "/kb/" },
  { exact: "/admin" },
  { prefix: "/admin/" },
  { exact: "/settings" },
  { prefix: "/settings/" },
];

function isAllowedPath(path: string): boolean {
  const normalized = path.replace(/\/+/g, "/");
  for (const rule of ALLOWED) {
    if (rule.exact !== undefined && normalized === rule.exact) return true;
    if (rule.prefix !== undefined && normalized.startsWith(rule.prefix)) return true;
  }
  return false;
}

/**
 * Returns a safe redirect path for post-login navigation.
 * - Decodes the redirect param once to prevent encoded external URLs.
 * - Rejects: protocol (e.g. http:, javascript:), hostname (//), query/hash tricks, control chars.
 * - Allows only: /chat, /kb, /kb/*, /admin, /admin/*, /settings, /settings/*.
 */
export function getSafeLoginRedirect(redirect: string | null | undefined): string {
  if (redirect == null || typeof redirect !== "string") return DEFAULT_REDIRECT;
  let path = redirect.trim();
  if (!path) return DEFAULT_REDIRECT;

  try {
    path = decodeURIComponent(path);
  } catch {
    return DEFAULT_REDIRECT;
  }

  if (!path.startsWith("/") || path.startsWith("//")) return DEFAULT_REDIRECT;
  if (path.includes("://")) return DEFAULT_REDIRECT;
  if (/[\0\r\n]/.test(path)) return DEFAULT_REDIRECT;
  if (path.includes("javascript:") || path.includes("data:") || path.toLowerCase().includes("vbscript:")) return DEFAULT_REDIRECT;

  const withoutQuery = path.split("?")[0].split("#")[0];
  const clean = withoutQuery.replace(/\/+/g, "/").replace(/\/$/, "") || "/";
  if (!isAllowedPath(clean)) return DEFAULT_REDIRECT;

  return clean;
}
