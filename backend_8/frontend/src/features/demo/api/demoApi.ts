/**
 * Host install API: slug ellenőrzés, tenant signup. Auth nem kell.
 */
import api from "../../../api/axiosClient";

const BASE = "";
const SLUG_CHECK_RETRY_DELAYS_MS = [250, 700];

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isTransientSlugCheckError(error: unknown): boolean {
  const candidate = error as {
    response?: { status?: number };
    code?: string;
    message?: string;
  };
  const status = candidate?.response?.status;
  if (status === 500 || status === 502 || status === 503 || status === 504) return true;
  return candidate?.code === "ECONNABORTED" || /network error/i.test(candidate?.message || "");
}

export interface CheckSlugResponse {
  available: boolean;
  slug: string;
  /** Backend config: a tenant cím domain része (pl. teappod.hu). A frontend ezt mutatja "A címed: slug.{tenant_base_domain}" */
  tenant_base_domain?: string;
}

export async function checkSlug(slug: string): Promise<CheckSlugResponse> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= SLUG_CHECK_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const { data } = await api.get<CheckSlugResponse>(`${BASE}/installer/check-slug`, {
        params: { slug },
      });
      return data;
    } catch (error) {
      lastError = error;
      if (attempt === SLUG_CHECK_RETRY_DELAYS_MS.length || !isTransientSlugCheckError(error)) {
        throw error;
      }
      await sleep(SLUG_CHECK_RETRY_DELAYS_MS[attempt]);
    }
  }
  throw lastError;
}

export interface DemoSignupBody {
  email: string;
  name: string;
  locale?: "hu" | "en" | "es";
  resend_existing_access?: boolean;
  kb_name?: string;
  company_name?: string;
  address?: string;
  phone?: string;
  plan_code?: string;
  billing_period?: string;
  demo_session_id: string;
}

export interface DemoSignupResponse {
  slug: string;
  message: string;
  host_hint: string;
  /** Üres, ha csak emailben küldtük (pl. új elérés kérése); ilyenkor nincs azonnali böngészős beléptetés. */
  demo_login_token: string;
  created_new: boolean;
  resent_existing: boolean;
}

export async function demoSignup(body: DemoSignupBody): Promise<DemoSignupResponse> {
  const { data } = await api.post<DemoSignupResponse>(`${BASE}/installer/tenant-signup`, body);
  return data;
}

export async function resolveDemoLogin(token: string): Promise<{ redirect_to: string }> {
  const { data } = await api.get<{ redirect_to: string }>(`${BASE}/installer/demo-login/resolve`, {
    params: { token },
  });
  return data;
}

export async function consumeDemoLogin(token: string): Promise<{ access_token: string }> {
  const { data } = await api.post<{ access_token: string }>("/auth/demo-login", { token });
  return data;
}

/**
 * Tudástár névből → slug (backend-kompatibilis). Ország kód egyelőre nincs.
 */
export function normalizeSlug(kbName: string): string {
  return (kbName || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z]/g, "")
    .toLowerCase()
    .slice(0, 48);
}
