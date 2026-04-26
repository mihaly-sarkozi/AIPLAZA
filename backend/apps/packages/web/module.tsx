import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "packages",
    routes: () => [
      {
        key: "packages.plans",
        path: "/admin/csomagok",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/packages/pages/PackagesPage"),
      },
      {
        key: "packages.checkout",
        path: "/admin/csomagok/fizetes",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/packages/pages/PackagesCheckoutPage"),
      },
      {
        key: "packages.addonCheckout",
        path: "/admin/csomagok/bovites-fizetes",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/packages/pages/PackagesAddonCheckoutPage"),
      },
      {
        key: "packages.upgradeCheckout",
        path: "/admin/csomagok/felfele-fizetes",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/packages/pages/PackagesUpgradeCheckoutPage"),
      },
    ],
    menuItems: () => [
      {
        key: "packages.menu",
        path: "/admin/csomagok",
        labelKey: "nav.packages",
        requiresAuth: true,
        requiredPermission: "settings.read",
        order: 45,
      },
    ],
  };
}
