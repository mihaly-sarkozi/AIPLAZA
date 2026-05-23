import api, { fetchPlatformAdminCsrfToken } from "../../api/axiosClient";
import { usePlatformAdminStore } from "./state";
import type {
  PlatformAdminLoginResponse,
  PlatformAdminStatisticsResponse,
  PlatformAdminSecurityMonitoringResponse,
  PlatformAdminTenantStatisticsDetail,
  PlatformAdminTenant,
  PlatformAdminUser,
} from "./types";

function authHeaders() {
  const token = usePlatformAdminStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function isUnauthorized(err: unknown): boolean {
  return !!(
    err &&
    typeof err === "object" &&
    "response" in err &&
    (err as { response?: { status?: number } }).response?.status === 401
  );
}

let platformAdminRefreshPromise: Promise<PlatformAdminLoginResponse> | null = null;

async function refreshPlatformAdminSessionSingleFlight(): Promise<PlatformAdminLoginResponse> {
  if (!platformAdminRefreshPromise) {
    platformAdminRefreshPromise = refreshPlatformAdminSession().finally(() => {
      platformAdminRefreshPromise = null;
    });
  }
  return platformAdminRefreshPromise;
}

async function withPlatformAdminRefresh<T>(request: () => Promise<T>): Promise<T> {
  try {
    return await request();
  } catch (err) {
    if (!isUnauthorized(err)) throw err;
    const refreshed = await refreshPlatformAdminSessionSingleFlight();
    usePlatformAdminStore.getState().setSession(refreshed.access_token, refreshed.user);
    return request();
  }
}

export async function platformAdminLogin(email: string, password: string): Promise<PlatformAdminLoginResponse> {
  await fetchPlatformAdminCsrfToken();
  const res = await api.post<PlatformAdminLoginResponse>("/platform-admin/auth/login", { email, password });
  return res.data;
}

export async function refreshPlatformAdminSession(): Promise<PlatformAdminLoginResponse> {
  await fetchPlatformAdminCsrfToken();
  const res = await api.post<PlatformAdminLoginResponse>("/platform-admin/auth/refresh", {});
  return res.data;
}

export async function platformAdminLogout(): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await api.post("/platform-admin/auth/logout", {});
}

export async function fetchActivePlatformTenants(): Promise<PlatformAdminTenant[]> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminTenant[]>("/platform-admin/tenants/active", { headers: authHeaders() });
    return res.data;
  });
}

export async function fetchPlatformAdminStatistics(): Promise<PlatformAdminStatisticsResponse> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminStatisticsResponse>("/platform-admin/statistics/overview", { headers: authHeaders() });
    return res.data;
  });
}

export async function fetchPlatformAdminTenantStatistics(tenantId: number): Promise<PlatformAdminTenantStatisticsDetail> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminTenantStatisticsDetail>(`/platform-admin/statistics/tenants/${tenantId}`, { headers: authHeaders() });
    return res.data;
  });
}

export async function fetchPlatformAdminSecurityMonitoring(): Promise<PlatformAdminSecurityMonitoringResponse> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminSecurityMonitoringResponse>("/platform-admin/monitoring/security", { headers: authHeaders() });
    return res.data;
  });
}

export async function banPlatformSecurityIp(payload: {
  ip: string;
  reason?: string;
  expires_hours?: number;
}): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.post("/platform-admin/monitoring/security/ban-ip", payload, { headers: authHeaders() });
  });
}

export async function unbanPlatformSecurityIp(ip: string): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.delete(`/platform-admin/monitoring/security/ban-ip/${encodeURIComponent(ip)}`, { headers: authHeaders() });
  });
}

export async function acknowledgePlatformSecurityAlert(alertId: number): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.post(`/platform-admin/monitoring/security/alerts/${alertId}/ack`, {}, { headers: authHeaders() });
  });
}

export async function updatePlatformAdminProfile(payload: { name: string }): Promise<PlatformAdminUser> {
  await fetchPlatformAdminCsrfToken();
  return withPlatformAdminRefresh(async () => {
    const res = await api.patch<PlatformAdminUser>("/platform-admin/auth/me", payload, { headers: authHeaders() });
    return res.data;
  });
}

export async function changePlatformAdminPassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.post("/platform-admin/auth/me/change-password", payload, { headers: authHeaders() });
  });
}


