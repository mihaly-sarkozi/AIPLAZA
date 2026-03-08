/**
 * Knowledge base (tudástár) API service. Used by React Query hooks; no React dependencies.
 */
import api from "../axiosClient";

export type KbItem = {
  uuid: string;
  name: string;
  description?: string;
  [key: string]: unknown;
};

export type CreateKbPayload = { name: string; description?: string };

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

export async function updateKb({ uuid, name, description }: UpdateKbPayload): Promise<KbItem> {
  const res = await api.put(`/kb/${uuid}`, { name, description });
  return res.data as KbItem;
}

export async function deleteKb({ uuid, confirm_name }: DeleteKbPayload): Promise<unknown> {
  const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
  return res.data;
}
