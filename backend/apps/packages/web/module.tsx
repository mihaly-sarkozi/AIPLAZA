import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "packages",
    routes: () => [
      {
        key: "packages.plans",
        path: "/admin/pricing",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/packages/pages/PackagesPage"),
      },
      {
        key: "packages.checkout",
        path: "/admin/pricing/checkout",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/packages/pages/PackagesCheckoutPage"),
      },
      {
        key: "packages.addonCheckout",
        path: "/admin/pricing/addon-checkout",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/packages/pages/PackagesAddonCheckoutPage"),
      },
      {
        key: "packages.upgradeCheckout",
        path: "/admin/pricing/upgrade-checkout",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        loader: () => import("@frontend/features/packages/pages/PackagesUpgradeCheckoutPage"),
      },
    ],
    menuItems: () => [
      {
        key: "packages.menu",
        path: "/admin/pricing",
        labelKey: "nav.packages",
        requiresAuth: true,
        requiredPermission: "billing.manage",
        order: 45,
      },
    ],
  };
}
