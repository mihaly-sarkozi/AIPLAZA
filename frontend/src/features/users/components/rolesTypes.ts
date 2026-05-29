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
  if (isDeletedUser(user)) return "bg-[var(--color-danger-text)]";
  if (!user.is_active) return "bg-slate-500";
  if (user.pending_registration) return "bg-amber-500";
  if (user.is_active) return "bg-[var(--color-success-text)]";
  return "bg-slate-500";
}
