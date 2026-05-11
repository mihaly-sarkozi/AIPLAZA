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
      {
        key: "billing.settleCheckout",
        path: "/admin/szamlak/kiegyenlites",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/billing/pages/BillingSettleCheckoutPage"),
      },
      {
        key: "billing.dateSimulation",
        path: "/admin/datum-szimulacio",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/billing/pages/BillingDateSimulationPage"),
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
