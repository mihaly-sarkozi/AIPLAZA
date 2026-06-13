// frontend/src/features/settings/model/settingsPermissions.ts
// Feladat: A settings oldal frontend jogosultsági döntéseinek központi, újrahasznosítható helye.
// Sárközi Mihály - 2026.05.29

import type { User } from "../../../store/authStore";

export function canAccessSettings(user: User | null | undefined): user is User {
  return Boolean(user && (user.role === "owner" || user.role === "admin"));
}

export function canManageBillingAndDomains(user: User | null | undefined): boolean {
  return canAccessSettings(user);
}

export function canResetTenant(user: User | null | undefined): boolean {
  return Boolean(user && user.role === "owner");
}
