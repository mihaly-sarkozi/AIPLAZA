import type { FrontendRole, FrontendUser } from "./moduleTypes";

const rolePermissions: Record<string, Set<string>> = {
  owner: new Set(["*"]),
  admin: new Set([
    "auth.login",
    "auth.refresh",
    "auth.logout",
    "chat.use",
    "knowledge.read",
    "knowledge.write",
    "knowledge.permissions.manage",
    "users.read",
    "users.write",
    "users.invite",
  ]),
  user: new Set([
    "auth.login",
    "auth.refresh",
    "auth.logout",
    "chat.use",
    "knowledge.read",
  ]),
};

export function hasRolePermission(role: FrontendRole | null | undefined, permission: string | undefined): boolean {
  const normalizedPermission = (permission || "").trim();
  if (!normalizedPermission) return true;
  const granted = rolePermissions[(role || "user").toString().trim().toLowerCase()] ?? new Set<string>();
  return granted.has("*") || granted.has(normalizedPermission);
}

export function hasUserPermission(user: FrontendUser | null | undefined, permission: string | undefined): boolean {
  if (!permission) return true;
  if (!user) return false;
  return hasRolePermission(user.role, permission);
}
