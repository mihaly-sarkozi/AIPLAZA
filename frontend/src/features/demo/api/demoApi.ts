/**
 * Nyilvános demo/install API: slug ellenőrzés, demo-signup. Auth nem kell.
 */
import api from "../../../api/axiosClient";

const BASE = "";

export interface CheckSlugResponse {
  available: boolean;
  slug: string;
  /** Backend config: a tenant cím domain része (pl. teappod.hu). A frontend ezt mutatja "A címed: slug.{tenant_base_domain}" */
  tenant_base_domain?: string;
}

export async function checkSlug(slug: string): Promise<CheckSlugResponse> {
  const { data } = await api.get<CheckSlugResponse>(`${BASE}/public/check-slug`, {
    params: { slug },
  });
  return data;
}

export interface DemoSignupBody {
  email: string;
  kb_name: string;
  name: string;
  company_name?: string;
  address?: string;
  phone?: string;
}

export interface DemoSignupResponse {
  slug: string;
  message: string;
  host_hint: string;
}

export async function demoSignup(body: DemoSignupBody): Promise<DemoSignupResponse> {
  const { data } = await api.post<DemoSignupResponse>(`${BASE}/public/demo-signup`, body);
  return data;
}

/**
 * Tudástár névből → slug (backend-kompatibilis). Ország kód egyelőre nincs.
 */
export function normalizeSlug(kbName: string): string {
  return (kbName || "")
    .replace(/[^a-zA-Z0-9\s\-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 64);
}
