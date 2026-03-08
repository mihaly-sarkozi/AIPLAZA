/**
 * Knowledge base (tudástár) API service. Used by React Query hooks; no React dependencies.
 */
import api from "../axiosClient";

export type KbItem = {
  uuid: string;
  name: string;
  description?: string;
  /** Aktuális user taníthatja-e (backend listánál kitölti) */
  can_train?: boolean;
  [key: string]: unknown;
};

export type KbPermissionItem = {
  user_id: number;
  email: string;
  name?: string | null;
  permission: string;
  role: "user" | "admin" | "owner";
};

export type CreateKbPayload = {
  name: string;
  description?: string;
  permissions?: Array<{ user_id: number; permission: string }>;
};

export type UpdateKbPayload = { uuid: string; name: string; description?: string };

export type DeleteKbPayload = { uuid: string; confirm_name: string };

export async function getKbList(): Promise<KbItem[]> {
  const res = await api.get("/kb");
  return res.data as KbItem[];
}

export async function createKb(body: CreateKbPayload): Promise<KbItem> {
  const res = await api.post("/kb", body);
  return res.data as KbItem;
}

export async function getKbPermissions(kbUuid: string): Promise<KbPermissionItem[]> {
  const res = await api.get(`/kb/${kbUuid}/permissions`);
  return res.data as KbPermissionItem[];
}

export async function setKbPermissions(
  kbUuid: string,
  permissions: Array<{ user_id: number; permission: string }>
): Promise<unknown> {
  const res = await api.put(`/kb/${kbUuid}/permissions`, { permissions });
  return res.data;
}

export async function updateKb({ uuid, name, description }: UpdateKbPayload): Promise<KbItem> {
  const res = await api.put(`/kb/${uuid}`, { name, description });
  return res.data as KbItem;
}

export async function deleteKb({ uuid, confirm_name }: DeleteKbPayload): Promise<unknown> {
  const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
  return res.data;
}
