// backend/apps/settings/web/module.tsx
// Feladat: A settings frontend moduldefiníciója. Regisztrálja az admin settings route-ot és menüpontot settings.read jogosultsággal.
// Sárközi Mihály - 2026.05.24

import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "settings",
    routes: () => [
      {
        key: "settings.page",
        path: "/admin/settings",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/settings/pages/SettingsPage"),
      },
    ],
    menuItems: () => [
      {
        key: "settings.system",
        path: "/admin/settings",
        labelKey: "nav.settings",
        requiresAuth: true,
        requiredPermission: "settings.read",
        order: 60,
      },
    ],
  };
}
