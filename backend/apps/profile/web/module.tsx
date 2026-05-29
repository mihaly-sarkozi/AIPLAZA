// backend/apps/profile/web/module.tsx
// Feladat: Frontend profile moduldefiníció a /profile és /change-password route-ok regisztrációjához.
// Sárközi Mihály - 2026.05.24

import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "profile",
    routes: () => [
      {
        key: "profile.page",
        path: "/profile",
        layout: "main",
        requiresAuth: true,
        loader: () => import("@frontend/features/profile/pages/ProfilePage"),
      },
      {
        key: "profile.change-password",
        path: "/change-password",
        layout: "main",
        requiresAuth: true,
        loader: () => import("@frontend/features/profile/pages/ChangePasswordPage"),
      },
    ],
    menuItems: () => [],
  };
}
