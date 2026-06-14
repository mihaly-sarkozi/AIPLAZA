import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { queryKeys } from "../../../queryKeys";
import {
  useMonitorIngestRuns,
  useProcessingEvents,
  useProcessingIssues,
  useProcessingMetrics,
  useUnderstandingStatus,
} from "./useKbProcessingMonitor";
import { computeMonitorPollInterval } from "../utils/processingMonitorPolling";
import type { ProcessingEventsPage } from "../../../api/services/kb/kbProcessingApi";
import type { IngestRun } from "../../../api/services/kb/types";

type MonitorScope = {
  trainingItemId?: string;
};

function useMonitorPollOptions(kbUuid: string | undefined, scope?: MonitorScope) {
  const queryClient = useQueryClient();

  return useMemo(() => {
    if (!kbUuid) {
      return { refetchInterval: false as const, refetchIntervalInBackground: false };
    }

    const resolvePollInterval = (): number | false => {
      const runs = queryClient.getQueryData<{ items: IngestRun[] }>([
        ...queryKeys.kbProcessingMonitor(kbUuid),
        "ingest-runs",
      ]);
      const eventsParams = scope?.trainingItemId ? { training_item_id: scope.trainingItemId } : {};
      const events = queryClient.getQueryData<ProcessingEventsPage>([
        ...queryKeys.kbProcessingMonitor(kbUuid),
        "events",
        eventsParams,
      ]);
      return computeMonitorPollInterval(runs?.items, events?.items, scope?.trainingItemId);
    };

    return {
      refetchInterval: resolvePollInterval,
      refetchIntervalInBackground: false,
    };
  }, [kbUuid, queryClient, scope?.trainingItemId]);
}

export function useProcessingMonitorBundle(kbUuid: string | undefined, scope?: MonitorScope) {
  const pollOptions = useMonitorPollOptions(kbUuid, scope);
  const eventsParams = scope?.trainingItemId
    ? { training_item_id: scope.trainingItemId }
    : undefined;
  const issuesParams = scope?.trainingItemId
    ? { training_item_id: scope.trainingItemId, status: "OPEN" }
    : undefined;

  const runsQuery = useMonitorIngestRuns(kbUuid, pollOptions);
  const eventsQuery = useProcessingEvents(kbUuid, eventsParams, pollOptions);
  const issuesQuery = useProcessingIssues(kbUuid, issuesParams, pollOptions);
  const metricsQuery = useProcessingMetrics(kbUuid, pollOptions);
  const understandingQuery = useUnderstandingStatus(
    kbUuid,
    scope?.trainingItemId,
    scope?.trainingItemId ? pollOptions : undefined,
  );

  const pollInterval = computeMonitorPollInterval(
    runsQuery.data?.items,
    eventsQuery.data?.items,
    scope?.trainingItemId,
  );

  return {
    runsQuery,
    eventsQuery,
    issuesQuery,
    metricsQuery,
    understandingQuery,
    isLive: pollInterval !== false,
    pollInterval,
  };
}
