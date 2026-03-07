import { create } from "zustand";
import api from "../api/axiosClient";

/**
 * Access token CSAK memóriában (NE localStorage/sessionStorage) – XSS esetén ne legyen lopható.
 * Refresh token csak HttpOnly cookie-ban (backend); subdomain izoláció: host-only cookie (tenant→tenant nem szivárog).
 */

/** Egyetlen folyamatban lévő /me kérés – Strict Mode / többszörös mount ne indítson több hívást */
let loadUserPromise: Promise<void> | null = null;

interface User {
  id: number;
  email: string;
  role: "user" | "admin" | "owner";
  name?: string | null;
  preferred_locale?: string | null;
  preferred_theme?: string | null;
  locale?: string;
  theme?: string;
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

  setToken: (token) => {
    set({ token });
  },

  setUser: (user) => set({ user }),

  loadUser: async () => {
    if (loadUserPromise) return loadUserPromise;

    loadUserPromise = (async () => {
      set({ loadingUser: true });
      try {
        let token = get().token;
        if (!token) {
          try {
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
