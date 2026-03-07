import { create } from "zustand";
import api from "../api/axiosClient";

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
  token: localStorage.getItem("access_token"),
  user: null,
  loadingUser: true,

  setToken: (token) => {
    if (token) localStorage.setItem("access_token", token);
    else localStorage.removeItem("access_token");
    set({ token });
  },

  setUser: (user) => set({ user }),

  loadUser: async () => {
    const token = get().token;
    if (!token) {
      set({ loadingUser: false });
      return;
    }
    if (loadUserPromise) return loadUserPromise;

    loadUserPromise = (async () => {
      set({ loadingUser: true });
      try {
        const res = await api.get("/auth/me");
        set({ user: res.data });
      } catch {
        set({ user: null, token: null });
        localStorage.removeItem("access_token");
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
    localStorage.removeItem("access_token");
  },
}));
