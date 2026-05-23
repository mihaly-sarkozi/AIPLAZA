import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "demo",
    routes: () => [
      {
        key: "demo.page",
        path: "/demo",
        layout: "public",
        loader: () => import("@frontend/features/demo/pages/DemoPage"),
      },
      {
        key: "demo.login",
        path: "/demo-login",
        layout: "public",
        loader: () => import("@frontend/features/demo/pages/DemoLoginPage"),
      },
      {
        key: "demo.expired",
        path: "/demo-expired",
        layout: "public",
        loader: () => import("@frontend/features/demo/pages/DemoExpiredPage"),
      },
      {
        key: "demo.email-sent",
        path: "/demo-email-sent",
        layout: "public",
        loader: () => import("@frontend/features/demo/pages/DemoEmailSentPage"),
      },
    ],
    menuItems: () => [],
  };
}
