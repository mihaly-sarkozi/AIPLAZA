import type { UserListItem } from "../hooks/useUsers";

export type RoleUser = UserListItem & { pending_registration?: boolean };

export type RoleFormData = {
  email: string;
  name: string;
  role: "user" | "admin";
  is_active: boolean;
};

export function isDeletedUser(user: RoleUser): boolean {
  return Boolean(user.deleted_at);
}

export function getStatusClasses(user: RoleUser): string {
  if (isDeletedUser(user)) return "bg-[var(--color-danger-text)] text-white";
  if (user.is_active) return "bg-[var(--color-success-text)] text-white";
  if (user.pending_registration) return "bg-amber-500 text-white";
  return "bg-slate-500 text-white";
}
