import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "orders",
    routes: () => [
      {
        key: "orders.page",
        path: "/admin/megrendeles",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/orders/pages/OrdersPage"),
      },
    ],
    menuItems: () => [],
  };
}
