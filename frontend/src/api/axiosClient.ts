import axios, { type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/authStore";
import { useLocaleStore } from "../i18n";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  withCredentials: true, // küldi a HttpOnly cookie-t (refresh tokenhez)
});

// 🔒 Token + Accept-Language minden kéréshez (backend hibák a kiválasztott nyelven)
api.interceptors.request.use((config) => {
  const locale = useLocaleStore.getState().locale;
  config.headers["Accept-Language"] = locale;

  const url = (config.url ?? "").toString();
  if (/^\/auth\/login(\/|$)/.test(url) || /^\/auth\/register(\/|$)/.test(url)) {
    return config;
  }
  const { token } = useAuthStore.getState();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Egyszerre csak egy refresh fut; a többi 401 erre vár, majd az új tokennel újrapróbálja
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const res = await api.post<{ access_token: string }>(
    "/auth/refresh",
    {},
    { withCredentials: true }
  );
  const newToken = res.data.access_token;
  useAuthStore.getState().setToken(newToken);
  return newToken;
}

const PERMISSIONS_CHANGED_CODE = "permissions_changed";

function getDetailMessage(err: unknown): string | undefined {
  const detail = err && typeof err === "object" && "response" in err
    ? (err as { response?: { data?: { detail?: { message?: string; code?: string } } } }).response?.data?.detail
    : undefined;
  return detail && typeof detail === "object" && "message" in detail ? detail.message : undefined;
}

function isPermissionsChanged(err: unknown): boolean {
  const detail = err && typeof err === "object" && "response" in err
    ? (err as { response?: { data?: { detail?: { code?: string } } } }).response?.data?.detail
    : undefined;
  return !!(detail && typeof detail === "object" && detail.code === PERMISSIONS_CHANGED_CODE);
}

function redirectToLogin(err?: unknown): void {
  if (typeof window !== "undefined" && isPermissionsChanged(err)) {
    const msg = getDetailMessage(err) ?? "Változás történt a jogosultságokban. Jelentkezz be újra.";
    alert(msg);
  }
  useAuthStore.getState().logout();
  const returnPath = typeof window !== "undefined" ? window.location.pathname : "/chat";
  const path = returnPath && returnPath !== "/login" ? returnPath : "";
  window.location.href = path ? `/login?redirect=${encodeURIComponent(path)}` : "/login";
}

// 🔁 401 → előbb refresh token próba; ha az is 401 → kijelentkeztetés + login oldalra
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const url = (originalRequest?.url ?? "").toString();

    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    // Login/register 401: ne refresh-eljünk, hagyjuk a hibát
    if (/^\/auth\/login(\/|$)/.test(url) || /^\/auth\/register(\/|$)/.test(url)) {
      return Promise.reject(error);
    }
    // Ha maga a refresh kérés kapott 401-et (pl. törölt user, jogosultság változás) → üzenet ha kell, majd loginra
    if (/^\/auth\/refresh(\/|$)/.test(url)) {
      redirectToLogin(error);
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = doRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;

      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return api(originalRequest);
    } catch (refreshError) {
      redirectToLogin(refreshError);
      return Promise.reject(refreshError);
    }
  }
);

export default api;
