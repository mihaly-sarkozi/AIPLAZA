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
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KBList"),
      },
      {
        key: "knowledge.create",
        path: "/kb/create",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        redirectTo: "/kb",
        redirectState: { openKbCreate: true },
      },
      {
        key: "knowledge.edit",
        path: "/kb/edit/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KBEdit"),
      },
      {
        key: "knowledge.ingest",
        path: "/kb/ingest/:uuid",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngest"),
      },
      {
        key: "knowledge.ingestRunDetail",
        path: "/kb/ingest/:uuid/runs/:runId",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KBIngestRunDetail"),
      },
      {
        key: "knowledge.trace",
        path: "/knowledge/trace/:runId",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KnowledgeTracePage"),
      },
      {
        key: "knowledge.traceLatest",
        path: "/knowledge/trace/latest",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/KnowledgeLatestTracePage"),
      },
      {
        key: "knowledge.pipelineHealth",
        path: "/knowledge/pipeline-health/:runId",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/PipelineHealthTracePage"),
      },
      {
        key: "knowledge.pipelineHealthLatest",
        path: "/knowledge/pipeline-health/latest",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/PipelineHealthLatestTracePage"),
      },
      {
        key: "knowledge.onboardingTrain",
        path: "/onboarding/train",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        loader: () => import("@frontend/features/knowledge-base/pages/DemoOnboardingTrainPage"),
      },
    ],
    menuItems: () => [
      {
        key: "knowledge.menu",
        path: "/kb",
        labelKey: "nav.knowledgeBase",
        requiresAuth: true,
        requiredPermission: "knowledge.write",
        order: 20,
      },
    ],
    preload: ({ user }) => {
      if (!user) return;
      void import("@frontend/features/knowledge-base/pages/KBList");
      void import("@frontend/features/knowledge-base/pages/KBEdit");
      void import("@frontend/features/knowledge-base/pages/KBIngest");
      void import("@frontend/features/knowledge-base/pages/KBIngestRunDetail");
      void import("@frontend/features/knowledge-base/pages/KnowledgeTracePage");
      void import("@frontend/features/knowledge-base/pages/PipelineHealthTracePage");
    },
  };
}
