/**
 * Knowledge base (tudástár) API service. Used by React Query hooks; no React dependencies.
 */
import api from "../axiosClient";

export type PersonalDataMode = "no_personal_data" | "with_confirmation" | "allowed_not_to_ai";
export type PersonalDataSensitivity = "weak" | "medium" | "strong";

export type KbItem = {
  uuid: string;
  name: string;
  description?: string;
  personal_data_mode: PersonalDataMode;
  personal_data_sensitivity: PersonalDataSensitivity;
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

export type UpdateKbPayload = {
  uuid: string;
  name: string;
  description?: string;
  personal_data_mode: PersonalDataMode;
  personal_data_sensitivity: PersonalDataSensitivity;
};

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

export async function updateKb({
  uuid,
  name,
  description,
  personal_data_mode,
  personal_data_sensitivity,
}: UpdateKbPayload): Promise<KbItem> {
  const res = await api.put(`/kb/${uuid}`, {
    name,
    description,
    personal_data_mode,
    personal_data_sensitivity,
  });
  return res.data as KbItem;
}

export async function deleteKb({ uuid, confirm_name }: DeleteKbPayload): Promise<unknown> {
  const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
  return res.data;
}

export type KbTrainingLogEntry = {
  point_id: string;
  user_id: number | null;
  user_display: string;
  title: string;
  content: string | null;
  created_at: string | null;
};

export async function getKbTrainingLog(kbUuid: string): Promise<KbTrainingLogEntry[]> {
  const res = await api.get(`/kb/${kbUuid}/train/log`);
  return res.data as KbTrainingLogEntry[];
}

export async function deleteKbTrainingPoint(kbUuid: string, pointId: string): Promise<void> {
  await api.delete(`/kb/${kbUuid}/train/points/${pointId}`);
}
