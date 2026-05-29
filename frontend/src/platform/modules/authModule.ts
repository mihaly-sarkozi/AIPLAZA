import type { FrontendModuleDefinition } from "../moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "auth",
    routes: () => [
      {
        key: "auth.login",
        path: "/login",
        layout: "public",
        loader: () => import("@frontend/features/auth/pages/LoginPage"),
      },
      {
        key: "auth.forgot",
        path: "/forgot",
        layout: "public",
        loader: () => import("@frontend/features/auth/pages/ForgotPasswordPage"),
      },
      {
        key: "auth.set-password",
        path: "/set-password",
        layout: "public",
        loader: () => import("@frontend/features/auth/pages/SetPasswordPage"),
      },
      {
        key: "auth.confirm-email",
        path: "/confirm-email",
        layout: "public",
        loader: () => import("@frontend/features/auth/pages/ConfirmEmailPage"),
      },
      {
        key: "auth.service-deleted",
        path: "/service-deleted",
        layout: "public",
        loader: () => import("@frontend/features/auth/pages/ServiceDeletedPage"),
      },
    ],
    menuItems: () => [],
  };
}
