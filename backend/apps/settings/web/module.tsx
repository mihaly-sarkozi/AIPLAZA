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
