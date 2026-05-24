export type AuthRefreshCoordinator = {
  refresh: () => Promise<string>;
  reset: () => void;
};

type AuthRefreshCoordinatorOptions = {
  refreshAccessToken: () => Promise<string>;
  onRefreshFailure?: (error: unknown) => void;
};

export function createAuthRefreshCoordinator({
  refreshAccessToken,
  onRefreshFailure,
}: AuthRefreshCoordinatorOptions): AuthRefreshCoordinator {
  let refreshPromise: Promise<string> | null = null;

  return {
    refresh: () => {
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken()
          .catch((error) => {
            onRefreshFailure?.(error);
            throw error;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }
      return refreshPromise;
    },
    reset: () => {
      refreshPromise = null;
    },
  };
}
