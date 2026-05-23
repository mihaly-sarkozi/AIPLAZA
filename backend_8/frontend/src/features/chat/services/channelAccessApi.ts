import api, { fetchCsrfToken } from "../../../api/axiosClient";

export type ChannelCredentialItem = {
  id: number;
  channel_type: string;
  name: string;
  key_prefix: string;
  status: string;
  allowed_kb_uuids: string[];
  daily_limit: number;
  per_minute_limit: number;
  allowed_origins: string[];
  expires_at?: string | null;
  last_used_at?: string | null;
  created_at?: string | null;
};

export type ChannelCredentialCreatePayload = {
  channel_type: "widget" | "api";
  name: string;
  allowed_kb_uuids: string[];
  daily_limit: number;
  per_minute_limit: number;
  allowed_origins: string[];
  expires_at?: string | null;
};

export async function listChannelCredentials(): Promise<ChannelCredentialItem[]> {
  const res = await api.get<{ items: ChannelCredentialItem[] }>("/channel/credentials");
  return res.data.items || [];
}

export async function createChannelCredential(payload: ChannelCredentialCreatePayload): Promise<{
  id: number;
  secret: string;
  key_prefix: string;
}> {
  await fetchCsrfToken();
  const res = await api.post<{ item: { id: number; secret: string; key_prefix: string } }>("/channel/credentials", payload);
  return res.data.item;
}

export async function rotateChannelCredential(credentialId: number): Promise<{ secret: string }> {
  await fetchCsrfToken();
  const res = await api.post<{ item: { secret: string } }>(`/channel/credentials/${credentialId}/rotate`, {});
  return res.data.item;
}

export async function revokeChannelCredential(credentialId: number): Promise<void> {
  await fetchCsrfToken();
  await api.post(`/channel/credentials/${credentialId}/revoke`, {});
}

export async function getChannelInstructions(credentialId: number): Promise<{
  endpoint: string;
  widget_embed_snippet: string;
  api_example: { curl: string };
}> {
  const res = await api.get(`/channel/credentials/${credentialId}/instructions`);
  return res.data;
}

export async function getChannelAnalyticsSummary(days = 14): Promise<Record<string, unknown>> {
  const res = await api.get("/channel/analytics/summary", { params: { days } });
  return res.data.summary || {};
}
