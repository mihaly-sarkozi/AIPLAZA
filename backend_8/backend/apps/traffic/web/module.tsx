import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "traffic",
    routes: () => [
      {
        key: "traffic.page",
        path: "/admin/forgalom",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/traffic/pages/TrafficPage"),
      },
    ],
    menuItems: () => [
      {
        key: "traffic.menu",
        path: "/admin/forgalom",
        labelKey: "nav.traffic",
        requiresAuth: true,
        requiredPermission: "settings.read",
        order: 35,
      },
    ],
  };
}
