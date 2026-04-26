import { create } from "zustand";
import api, { fetchCsrfToken } from "../../../api/axiosClient";

/**
 * Authentication state – access token in memory only.
 *
 * ACCESS TOKEN:
 * - Stored ONLY in this in-memory store (Zustand state). Cleared on page reload.
 * - MUST NOT be written to localStorage, sessionStorage, or IndexedDB (XSS would expose it).
 * - Axios interceptor reads the token from this store only; never from browser storage.
 *
 * REFRESH TOKEN:
 * - Stored in HttpOnly Secure SameSite cookie by the backend. Not readable by JS.
 * - Sent automatically with credentials; used by POST /auth/refresh to get a new access token.
 */

let loadUserPromise: Promise<void> | null = null;

export interface User {
  id: number;
  email: string;
  role: "user" | "admin" | "owner";
  /** false: fiók zárolt / inaktív */
  is_active?: boolean;
  name?: string | null;
  preferred_locale?: string | null;
  preferred_theme?: string | null;
  locale?: string;
  theme?: string;
  /** False until the user sets a real password (e.g. demo magic-link users). */
  credentials_password_set?: boolean;
  tenant_demo_mode?: boolean;
  /** Van-e már betanított anyag a tenant tudástárában (billing alapján). */
  tenant_kb_has_training?: boolean;
}

/** Demo tenant user who has not set a password yet — show “set password” instead of “change password”. */
export function isDemoInitialPasswordMode(user: User | null | undefined): boolean {
  return user?.tenant_demo_mode === true && user?.credentials_password_set === false;
}

interface AuthState {
  token: string | null;
  user: User | null;
  loadingUser: boolean;
  setToken: (t: string | null) => void;
  setUser: (u: User | null) => void;
  loadUser: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  loadingUser: true,

  setToken: (token) => set({ token }),

  setUser: (user) => set({ user }),

  loadUser: async () => {
    if (loadUserPromise) return loadUserPromise;

    loadUserPromise = (async () => {
      set({ loadingUser: true });
      try {
        let token = get().token;
        if (!token) {
          try {
            await fetchCsrfToken();
            const refreshRes = await api.post<{ access_token: string }>("/auth/refresh", {}, { withCredentials: true });
            token = refreshRes.data.access_token;
            set({ token });
          } catch {
            set({ user: null, token: null, loadingUser: false });
            loadUserPromise = null;
            return;
          }
        }
        const res = await api.get("/auth/me");
        set({ user: res.data });
      } catch {
        set({ user: null, token: null });
      } finally {
        set({ loadingUser: false });
        loadUserPromise = null;
      }
    })();
    return loadUserPromise;
  },

  logout: () => {
    loadUserPromise = null;
    api.post("/auth/logout").catch(() => {});
    set({ user: null, token: null });
  },
}));
