import { create } from "zustand";
import api from "../api/axiosClient";

interface User {
  id: number;
  email: string;
  role: "user" | "admin";
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

    try {
      const res = await api.get("/auth/me");
      set({ user: res.data });
    } catch {
      set({ user: null, token: null });
      localStorage.removeItem("access_token");
    } finally {
      set({ loadingUser: false });
    }
  },

  logout: () => {
    api.post("/auth/logout").catch(() => {});
    set({ user: null, token: null });
    localStorage.removeItem("access_token");
  },
}));
