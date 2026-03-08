/**
 * User and auth/me API service. Used by React Query hooks; no React dependencies.
 */
import api from "../axiosClient";

export type UserListItem = {
  id: number;
  email: string;
  name?: string | null;
  role: string;
  is_active: boolean;
  created_at?: string;
  [key: string]: unknown;
};

export type UpdateUserPayload = {
  id: number;
  name?: string;
  is_active?: boolean;
  email?: string;
  role?: string;
};

export type PatchMePayload = {
  name?: string | null;
  preferred_locale?: string;
  preferred_theme?: string;
};

export type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

export async function getUsers(): Promise<UserListItem[]> {
  const res = await api.get("/users");
  return res.data as UserListItem[];
}

export async function createUser(body: {
  email: string;
  name?: string;
  role: string;
}): Promise<UserListItem> {
  const res = await api.post("/users", body);
  return res.data as UserListItem;
}

export async function updateUser({ id, ...body }: UpdateUserPayload): Promise<UserListItem> {
  const res = await api.put(`/users/${id}`, body);
  return res.data as UserListItem;
}

export async function deleteUser(userId: number): Promise<unknown> {
  const res = await api.delete(`/users/${userId}`);
  return res.data;
}

export async function resendInvite(userId: number): Promise<unknown> {
  const res = await api.post(`/users/${userId}/resend-invite`);
  return res.data;
}

export async function patchMe(
  body: PatchMePayload
): Promise<{ name?: string; preferred_locale?: string; preferred_theme?: string }> {
  const res = await api.patch("/auth/me", body);
  return res.data as { name?: string; preferred_locale?: string; preferred_theme?: string };
}

export async function changePassword(body: ChangePasswordPayload): Promise<unknown> {
  const res = await api.post("/auth/me/change-password", body);
  return res.data;
}
