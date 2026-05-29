import type { FrontendModuleDefinition } from "../moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "users",
    routes: () => [
      {
        key: "users.roles",
        path: "/admin/roles",
        layout: "main",
        requiresAuth: true,
        loader: () => import("@frontend/features/users/pages/RolesPage"),
      },
    ],
    menuItems: () => [
      {
        key: "users.roles.menu",
        path: "/admin/roles",
        labelKey: "nav.permissions",
        requiresAuth: true,
        requiredPermission: "users.write",
        order: 50,
      },
    ],
  };
}
