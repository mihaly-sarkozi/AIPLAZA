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
  kbIngestRuns: (uuid: string) => ["kb", uuid, "ingest", "runs"] as readonly unknown[],
  kbIngestRun: (runId: string) => ["kb", "ingest", "run", runId] as const,
  kbTrainingBatch: (batchId: string) => ["kb", "training", "batch", batchId] as const,
  kbProcessingMonitor: (uuid: string) => ["kb", uuid, "processing-monitor"] as const,
  settings: ["settings"] as const,
  settingsBilling: ["settings", "billing"] as const,
  settingsLocale: ["settings", "locale"] as const,
  settingsTwoFactor: ["settings", "security", "2fa"] as const,
  authenticatorStatus: ["auth", "authenticator", "status"] as const,
  domainOverview: ["platform", "domain", "overview"] as const,
  billingAccessStatus: ["billing", "accessStatus"] as const,
  billingOverview: ["billing", "overview"] as const,
  billingUpgradePreview: (planCode: string, billingPeriod: string) => ["billing", "upgradePreview", planCode, billingPeriod] as const,
} as const;
