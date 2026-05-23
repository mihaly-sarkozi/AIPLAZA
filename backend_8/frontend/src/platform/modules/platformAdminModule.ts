import type { FrontendModuleDefinition } from "../moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "platform-admin",
    routes: () => [
      {
        key: "platform-admin.login",
        path: "/platform-admin/login",
        layout: "public",
        loader: () => import("@frontend/features/platform-admin/pages/PlatformAdminLoginPage"),
      },
      {
        key: "platform-admin.dashboard",
        path: "/platform-admin",
        layout: "public",
        loader: () => import("@frontend/features/platform-admin/pages/PlatformAdminDashboardPage"),
      },
      {
        key: "platform-admin.statistics",
        path: "/platform-admin/statistics",
        layout: "public",
        loader: () => import("@frontend/features/platform-admin/pages/PlatformAdminStatisticsPage"),
      },
      {
        key: "platform-admin.statistics.tenant",
        path: "/platform-admin/statistics/tenants/:tenantId",
        layout: "public",
        loader: () => import("@frontend/features/platform-admin/pages/PlatformAdminTenantStatisticsDetailPage"),
      },
      {
        key: "platform-admin.monitoring.security",
        path: "/platform-admin/monitoring/security",
        layout: "public",
        loader: () => import("@frontend/features/platform-admin/pages/PlatformAdminSecurityMonitoringPage"),
      },
    ],
    menuItems: () => [],
  };
}

