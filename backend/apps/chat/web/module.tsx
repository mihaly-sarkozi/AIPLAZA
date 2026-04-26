import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "chat",
    routes: () => [
      {
        key: "chat.page",
        path: "/chat",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "chat.use",
        loader: () => import("@frontend/features/chat/pages/ChatPage"),
      },
    ],
    menuItems: () => [
      {
        key: "chat.menu",
        path: "/chat",
        labelKey: "nav.chat",
        requiresAuth: true,
        requiredPermission: "chat.use",
        order: 10,
      },
    ],
  };
}
