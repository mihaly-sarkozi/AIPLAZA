import { create } from "zustand";

import api, { fetchPlatformAdminCsrfToken } from "../../api/axiosClient";
import type { PlatformAdminLoginResponse, PlatformAdminUser } from "./types";

let loadPlatformAdminUserPromise: Promise<void> | null = null;

type PlatformAdminState = {
  token: string | null;
  user: PlatformAdminUser | null;
  loadingUser: boolean;
  setSession: (token: string, user: PlatformAdminUser) => void;
  setUser: (user: PlatformAdminUser | null) => void;
  clearSession: () => void;
  loadUser: () => Promise<void>;
  logout: () => Promise<void>;
};

export const usePlatformAdminStore = create<PlatformAdminState>((set, get) => ({
  token: null,
  user: null,
  loadingUser: true,

  setSession: (token, user) => set({ token, user, loadingUser: false }),
  setUser: (user) => set({ user }),
  clearSession: () => set({ token: null, user: null, loadingUser: false }),

  loadUser: async () => {
    if (loadPlatformAdminUserPromise) return loadPlatformAdminUserPromise;

    loadPlatformAdminUserPromise = (async () => {
      set({ loadingUser: true });
      try {
        let token = get().token;
        if (!token) {
          await fetchPlatformAdminCsrfToken();
          const res = await api.post<PlatformAdminLoginResponse>("/platform-admin/auth/refresh", {});
          const refreshed = res.data;
          token = refreshed.access_token;
          set({ token, user: refreshed.user });
        }
        await fetchPlatformAdminCsrfToken();
        const res = await api.get<PlatformAdminUser>("/platform-admin/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        set({ user: res.data });
      } catch {
        get().clearSession();
      } finally {
        set({ loadingUser: false });
        loadPlatformAdminUserPromise = null;
      }
    })();
    return loadPlatformAdminUserPromise;
  },

  logout: async () => {
    loadPlatformAdminUserPromise = null;
    try {
      await fetchPlatformAdminCsrfToken();
      await api.post("/platform-admin/auth/logout", {});
    } catch {
      // Kliens oldalon akkor is kiléptetünk, ha a szerver session már lejárt.
    } finally {
      get().clearSession();
    }
  },
}));

