import { QueryClient } from "@tanstack/react-query";

/** Don't retry on 4xx except rate limit / timeout (allow retry on 429, 408) */
function retryCondition(failureCount: number, error: unknown): boolean {
  const max = 3;
  if (failureCount >= max) return false;
  const status = error && typeof error === "object" && "response" in error
    ? (error as { response?: { status?: number } }).response?.status
    : undefined;
  if (status != null && status >= 400 && status < 500 && status !== 408 && status !== 429) return false;
  return true;
}

/** Exponential backoff: 1s, 2s, 4s (capped) */
function retryDelay(failureCount: number): number {
  const delay = Math.min(1000 * 2 ** failureCount, 10000);
  return delay;
}

/**
 * React Query client with global scalability defaults:
 * - Caching: 1min stale, 5min gc; refetch on window focus and reconnect
 * - Retry: up to 3 attempts with exponential backoff, no retry on 4xx (except 429/408)
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: (failureCount, error) => failureCount < 3 && retryCondition(failureCount, error),
      retryDelay,
      structuralSharing: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
