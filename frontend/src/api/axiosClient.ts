/**
 * Axios instance for API calls. Global retry strategy is applied in React Query (queryClient):
 * queries retry with exponential backoff; direct axios calls (auth, CSRF) are not retried.
 */
import axios, { type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/authStore";
import { getSafeLoginRedirect } from "../utils/loginRedirect";
import { getCsrfToken, setCsrfToken } from "../utils/csrf";
import { useLocaleStore } from "../i18n";
import { getApiErrorMessage } from "../utils/getApiErrorMessage";

// Dev proxy: baseURL legyen relatív (/api), hogy a kérés ugyanarra az originra menjen → refresh_token cookie (SameSite=Lax) elküldésre kerül.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  withCredentials: true, // küldi a HttpOnly cookie-t (refresh tokenhez)
});

// 🔒 Request interceptor: Authorization from auth store; X-CSRF-Token for state-changing methods.
api.interceptors.request.use((config) => {
  const locale = useLocaleStore.getState().locale;
  config.headers["Accept-Language"] = locale;

  const method = (config.method ?? "get").toLowerCase();
  if (["post", "patch", "put", "delete"].includes(method)) {
    const csrf = getCsrfToken();
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }

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

function isPermissionsChanged(err: unknown): boolean {
  const detail = err && typeof err === "object" && "response" in err
    ? (err as { response?: { data?: { detail?: { code?: string } } } }).response?.data?.detail
    : undefined;
  return !!(detail && typeof detail === "object" && detail.code === PERMISSIONS_CHANGED_CODE);
}

function redirectToLogin(err?: unknown): void {
  if (typeof window !== "undefined" && isPermissionsChanged(err)) {
    const msg = getApiErrorMessage(err) ?? "Változás történt a jogosultságokban. Jelentkezz be újra.";
    alert(msg);
  }
  useAuthStore.getState().logout();
  if (typeof window === "undefined") return;
  const pathname = window.location.pathname || "";
  // Már login/forgot/set-password oldalon vagyunk → ne töltődjön újra (különben refresh 401 → logout → reload → végtelen ciklus)
  if (pathname === "/login" || pathname.startsWith("/forgot") || pathname.startsWith("/set-password")) return;
  const path = getSafeLoginRedirect(pathname && pathname !== "/login" ? pathname : null);
  window.location.href = path !== "/chat" ? `/login?redirect=${encodeURIComponent(path)}` : "/login";
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

/** Fetch CSRF token on app init; store in memory. Call once before any state-changing request. */
export async function fetchCsrfToken(): Promise<void> {
  try {
    const res = await api.get<{ csrf_token: string }>("/auth/csrf-token", { withCredentials: true });
    if (res.data?.csrf_token) setCsrfToken(res.data.csrf_token);
  } catch {
    setCsrfToken(null);
  }
}

export default api;
