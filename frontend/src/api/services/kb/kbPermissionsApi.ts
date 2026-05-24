import api from "../../axiosClient";
import type { KbPermissionItem, KbPermissionsBatchResponse } from "./types";

export async function getKbPermissions(kbUuid: string): Promise<KbPermissionItem[]> {
  const res = await api.get(`/kb/${kbUuid}/permissions`);
  return res.data as KbPermissionItem[];
}

export async function getKbPermissionsBatch(kbUuids: string[]): Promise<KbPermissionsBatchResponse> {
  const unique = Array.from(new Set((kbUuids || []).map((x) => (x || "").trim()).filter(Boolean)));
  if (unique.length === 0) return {};
  const res = await api.post("/kb/permissions/batch", { uuids: unique });
  return (res.data || {}) as KbPermissionsBatchResponse;
}

export async function setKbPermissions(
  kbUuid: string,
  permissions: Array<{ user_id: number; permission: string }>
): Promise<unknown> {
  const res = await api.put(`/kb/${kbUuid}/permissions`, { permissions });
  return res.data;
}
