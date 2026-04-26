/**
 * Centralized React Query keys. Use these in hooks and invalidateQueries to keep cache consistent.
 */
export const queryKeys = {
  users: ["users"] as const,
  user: (id: number) => ["user", id] as const,
  authMe: ["auth", "me"] as const,
  profile: ["profile"] as const,
  profilePreferences: ["profile", "preferences"] as const,
  kb: ["kb"] as const,
  kbItem: (uuid: string) => ["kb", uuid] as const,
  kbIngestRuns: (uuid: string) => ["kb", uuid, "ingest", "runs"] as const,
  kbIngestRun: (runId: string) => ["kb", "ingest", "run", runId] as const,
  settings: ["settings"] as const,
  billingOverview: ["billing", "overview"] as const,
  billingUpgradePreview: (planCode: string, billingPeriod: string) => ["billing", "upgradePreview", planCode, billingPeriod] as const,
} as const;
