import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "knowledge",
    routes: () => [
      {
        key: "knowledge.list",
        path: "/kb",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBList"),
      },
      {
        key: "knowledge.create",
        path: "/kb/create",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "billing.read",
        redirectTo: "/kb",
        redirectState: { openKbCreate: true },
      },
      {
        key: "knowledge.edit",
        path: "/kb/edit/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBEdit"),
      },
      {
        key: "knowledge.ingest",
        path: "/kb/ingest/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngest"),
      },
      {
        key: "knowledge.ingestRunDetail",
        path: "/kb/ingest/:uuid/runs/:runId",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngestRunDetail"),
      },
      {
        key: "knowledge.onboardingTrain",
        path: "/onboarding/train",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
        loader: () => import("@frontend/features/knowledge-base/pages/DemoOnboardingTrainPage"),
      },
      {
        key: "knowledge.trainingTest",
        path: "/kb/training-test",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "kb.train",
        loader: () => import("@frontend/features/knowledge-base/pages/KbTrainingTestPage"),
      },
    ],
    menuItems: () => [
      {
        key: "knowledge.menu",
        path: "/kb",
        labelKey: "nav.knowledgeBase",
        requiresAuth: true,
        requiredPermission: "knowledge.read",
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
