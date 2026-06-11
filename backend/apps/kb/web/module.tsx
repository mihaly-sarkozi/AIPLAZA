import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "kb",
    routes: () => [
      {
        key: "kb.list",
        path: "/kb",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBList"),
      },
      {
        key: "kb.create",
        path: "/kb/create",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.read",
        redirectTo: "/kb",
        redirectState: { openKbCreate: true },
      },
      {
        key: "kb.edit",
        path: "/kb/edit/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBEdit"),
      },
      {
        key: "kb.ingest",
        path: "/kb/ingest/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngest"),
      },
      {
        key: "kb.ingestRunDetail",
        path: "/kb/ingest/:uuid/runs/:runId",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngestRunDetail"),
      },
      {
        key: "kb.onboardingTrain",
        path: "/onboarding/train",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.read",
        loader: () => import("@frontend/features/knowledge-base/pages/DemoOnboardingTrainPage"),
      },
      {
        key: "kb.trainingTest",
        path: "/kb/training-test",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.train",
        loader: () => import("@frontend/features/knowledge-base/pages/KbTrainingTestPage"),
      },
    ],
    menuItems: () => [
      {
        key: "kb.menu",
        path: "/kb",
        labelKey: "nav.knowledgeBase",
        requiresAuth: true,
        requiredPermission: "kb.read",
        order: 20,
      },
    ],
    preload: ({ user }) => {
      if (!user) return;
      void import("@frontend/features/knowledge-base/pages/KBList");
      void import("@frontend/features/knowledge-base/pages/KBEdit");
      void import("@frontend/features/knowledge-base/pages/KBIngest");
      void import("@frontend/features/knowledge-base/pages/KBIngestRunDetail");
    },
  };
}
