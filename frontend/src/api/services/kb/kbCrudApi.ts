import api from "../../axiosClient";
import type { CreateKbPayload, DeleteKbPayload, KbItem, UpdateKbPayload } from "./types";

export async function getKbList(): Promise<KbItem[]> {
  const res = await api.get("/kb");
  return res.data as KbItem[];
}

export async function createKb(body: CreateKbPayload): Promise<KbItem> {
  const res = await api.post("/kb", body);
  return res.data as KbItem;
}

export async function updateKb({
  uuid,
  name,
  description,
  personal_data_mode,
  pii_depersonalization_enabled,
  public_enabled,
}: UpdateKbPayload): Promise<KbItem> {
  const body: Record<string, unknown> = {
    name,
    description,
  };
  if (personal_data_mode) {
    body.personal_data_mode = personal_data_mode;
  }
  if (typeof pii_depersonalization_enabled === "boolean") {
    body.pii_depersonalization_enabled = pii_depersonalization_enabled;
  }
  if (typeof public_enabled === "boolean") {
    body.public_enabled = public_enabled;
  }
  const res = await api.put(`/kb/${uuid}`, body);
  return res.data as KbItem;
}

export async function deleteKb({ uuid, confirm_name }: DeleteKbPayload): Promise<unknown> {
  const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
  return res.data;
}
