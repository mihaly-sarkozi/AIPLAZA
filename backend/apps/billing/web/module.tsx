import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "billing",
    routes: () => [
      {
        key: "billing.invoices",
        path: "/admin/szamlak",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/billing/pages/BillingInvoicesPage"),
      },
    ],
    menuItems: () => [
      {
        key: "billing.menu",
        path: "/admin/szamlak",
        labelKey: "nav.invoices",
        requiresAuth: true,
        requiredPermission: "settings.read",
        order: 40,
      },
    ],
  };
}
