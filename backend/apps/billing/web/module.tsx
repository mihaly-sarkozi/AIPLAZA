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
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/billing/pages/BillingInvoicesPage"),
      },
      {
        key: "billing.settleCheckout",
        path: "/admin/szamlak/kiegyenlites",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/billing/pages/BillingSettleCheckoutPage"),
      },
    ],
    menuItems: () => [
      {
        key: "billing.menu",
        path: "/admin/szamlak",
        labelKey: "nav.invoices",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        order: 40,
      },
    ],
  };
}
