/**
 * Centralized React Query keys. Use these in hooks and invalidateQueries to keep cache consistent.
 */
export const queryKeys = {
  users: ["users"] as const,
  user: (id: number) => ["user", id] as const,
  authMe: ["auth", "me"] as const,
  kb: ["kb"] as const,
  kbItem: (uuid: string) => ["kb", uuid] as const,
} as const;
