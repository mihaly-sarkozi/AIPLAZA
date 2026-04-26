import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "profile",
    routes: () => [
      {
        key: "profile.page",
        path: "/profile",
        layout: "main",
        requiresAuth: true,
        loader: () => import("@frontend/features/profile/pages/ProfilePage"),
      },
      {
        key: "profile.change-password",
        path: "/change-password",
        layout: "main",
        requiresAuth: true,
        loader: () => import("@frontend/features/profile/pages/ChangePasswordPage"),
      },
    ],
    menuItems: () => [
      {
        key: "profile.changePassword.menu",
        path: "/change-password",
        labelKey: "nav.changePassword",
        requiresAuth: true,
        order: 60,
      },
    ],
  };
}
