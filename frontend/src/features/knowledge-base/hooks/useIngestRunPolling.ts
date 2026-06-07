import { getTrainingRunRefetchInterval } from "../utils/trainingProgress";
import { useIngestRun } from "./useKb";

export function useIngestRunPolling(runId: string | undefined) {
  return useIngestRun(runId, {
    refetchInterval: ({ state }) => getTrainingRunRefetchInterval(state.data?.status),
  });
}
