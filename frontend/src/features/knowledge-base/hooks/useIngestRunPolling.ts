import { ACTIVE_RUN_STATUSES } from "../pages/ingestLogHelpers";
import { useIngestRun } from "./useKb";

export function useIngestRunPolling(runId: string | undefined) {
  return useIngestRun(runId, {
    refetchInterval: ({ state }) => (ACTIVE_RUN_STATUSES.has(state.data?.status ?? "") ? 1500 : 4000),
  });
}
