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
