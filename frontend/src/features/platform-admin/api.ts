import api, { fetchPlatformAdminCsrfToken } from "../../api/axiosClient";
import { usePlatformAdminStore } from "./state";
import type {
  PlatformAdminLoginResponse,
  PlatformAdminStatisticsResponse,
  PlatformAdminSecurityMonitoringResponse,
  PlatformAdminTenantStatisticsDetail,
  PlatformAdminTenant,
  PlatformAdminAuditTrailResponse,
  PlatformAdminUser,
  PlatformAdminDebugDateResponse,
  PlatformAdminMfaStatusResponse,
  PlatformAdminMfaSetupResponse,
  PlatformAdminMfaConfirmResponse,
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
    try {
      const refreshed = await refreshPlatformAdminSessionSingleFlight();
      usePlatformAdminStore.getState().setSession(refreshed.access_token, refreshed.user);
      return request();
    } catch (refreshErr) {
      usePlatformAdminStore.getState().clearSession();
      throw refreshErr;
    }
  }
}

export async function platformAdminLogin(email: string, password: string, mfaCode?: string): Promise<PlatformAdminLoginResponse> {
  await fetchPlatformAdminCsrfToken();
  const payload = {
    email,
    password,
    mfa_code: mfaCode?.trim() || undefined,
  };
  const res = await api.post<PlatformAdminLoginResponse>("/platform-admin/auth/login", payload);
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

export async function fetchPlatformAdminMfaStatus(): Promise<PlatformAdminMfaStatusResponse> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminMfaStatusResponse>("/platform-admin/auth/mfa/status", { headers: authHeaders() });
    return res.data;
  });
}

export async function startPlatformAdminMfaSetup(): Promise<PlatformAdminMfaSetupResponse> {
  await fetchPlatformAdminCsrfToken();
  return withPlatformAdminRefresh(async () => {
    const res = await api.post<PlatformAdminMfaSetupResponse>("/platform-admin/auth/mfa/setup", {}, { headers: authHeaders() });
    return res.data;
  });
}

export async function confirmPlatformAdminMfaSetup(code: string): Promise<PlatformAdminMfaConfirmResponse> {
  await fetchPlatformAdminCsrfToken();
  return withPlatformAdminRefresh(async () => {
    const res = await api.post<PlatformAdminMfaConfirmResponse>("/platform-admin/auth/mfa/confirm", { code }, { headers: authHeaders() });
    return res.data;
  });
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

export async function restorePlatformAdminTenant(tenantId: number, confirmName: string): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.post(`/platform-admin/tenants/${tenantId}/restore`, { confirm_name: confirmName }, { headers: authHeaders() });
  });
}

export async function permanentlyDeletePlatformAdminTenant(tenantId: number, confirmName: string): Promise<void> {
  await fetchPlatformAdminCsrfToken();
  await withPlatformAdminRefresh(async () => {
    await api.post(`/platform-admin/tenants/${tenantId}/permanent-delete`, { confirm_name: confirmName }, { headers: authHeaders() });
  });
}

export async function fetchPlatformAdminTenantAuditTrail(params: {
  tenantId: number;
  fromDate?: string;
  toDate?: string;
  email?: string;
  actions?: string[];
  limit?: number;
  cursor?: string | null;
}): Promise<PlatformAdminAuditTrailResponse> {
  return withPlatformAdminRefresh(async () => {
    const search = new URLSearchParams();
    if (params.fromDate) search.set("from_date", params.fromDate);
    if (params.toDate) search.set("to_date", params.toDate);
    if (params.email?.trim()) search.set("email", params.email.trim());
    for (const action of params.actions || []) {
      search.append("action", action);
    }
    if (params.limit) search.set("limit", String(params.limit));
    if (params.cursor) search.set("cursor", params.cursor);
    const query = search.toString();
    const res = await api.get<PlatformAdminAuditTrailResponse>(
      `/platform-admin/audit/tenants/${params.tenantId}${query ? `?${query}` : ""}`,
      { headers: authHeaders() }
    );
    return res.data;
  });
}

export async function exportPlatformAdminTenantAuditTrail(params: {
  tenantId: number;
  fromDate?: string;
  toDate?: string;
  email?: string;
  actions?: string[];
}): Promise<void> {
  return withPlatformAdminRefresh(async () => {
    const search = new URLSearchParams();
    if (params.fromDate) search.set("from_date", params.fromDate);
    if (params.toDate) search.set("to_date", params.toDate);
    if (params.email?.trim()) search.set("email", params.email.trim());
    for (const action of params.actions || []) {
      search.append("action", action);
    }
    const query = search.toString();
    const res = await api.get<Blob>(
      `/platform-admin/audit/tenants/${params.tenantId}/export${query ? `?${query}` : ""}`,
      { headers: authHeaders(), responseType: "blob" }
    );
    const url = window.URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-trail-${params.tenantId}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  });
}

export async function fetchPlatformAdminSecurityMonitoring(): Promise<PlatformAdminSecurityMonitoringResponse> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminSecurityMonitoringResponse>("/platform-admin/monitoring/security", { headers: authHeaders() });
    return res.data;
  });
}

export async function fetchPlatformAdminDebugDate(): Promise<PlatformAdminDebugDateResponse> {
  return withPlatformAdminRefresh(async () => {
    const res = await api.get<PlatformAdminDebugDateResponse>("/platform-admin/debug/simulated-date", { headers: authHeaders() });
    return res.data;
  });
}

export async function updatePlatformAdminDebugDate(simulatedDate: string | null): Promise<PlatformAdminDebugDateResponse> {
  await fetchPlatformAdminCsrfToken();
  return withPlatformAdminRefresh(async () => {
    const res = await api.put<PlatformAdminDebugDateResponse>(
      "/platform-admin/debug/simulated-date",
      { simulated_date: simulatedDate },
      { headers: authHeaders() }
    );
    return res.data;
  });
}

export async function clearPlatformAdminDebugDate(): Promise<PlatformAdminDebugDateResponse> {
  await fetchPlatformAdminCsrfToken();
  return withPlatformAdminRefresh(async () => {
    const res = await api.delete<PlatformAdminDebugDateResponse>("/platform-admin/debug/simulated-date", { headers: authHeaders() });
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


