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
      {
        key: "chat.channelAccess",
        path: "/chat/channel-access",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "chat.channel.manage",
        loader: () => import("@frontend/features/chat/pages/ChatChannelAccessPage"),
      },
    ],
    menuItems: () => [
      {
        key: "chat.channelAccess.menu",
        path: "/chat/channel-access",
        labelKey: "nav.chatAccess",
        requiresAuth: true,
        requiredPermission: "chat.channel.manage",
        order: 11,
      },
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
