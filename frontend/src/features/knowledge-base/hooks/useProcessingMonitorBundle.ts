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
import {
  computeMonitorPollInterval,
  TENANT_MONITOR_EVENTS_PARAMS,
} from "../utils/processingMonitorPolling";
import type { ProcessingEventsPage } from "../../../api/services/kb/kbProcessingApi";
import type { IngestRun } from "../../../api/services/kb/types";

type MonitorScope = {
  trainingItemId?: string;
};

function readTenantEventsFromCache(
  queryClient: ReturnType<typeof useQueryClient>,
  kbUuid: string,
): ProcessingEventsPage | undefined {
  const monitorKey = queryKeys.kbProcessingMonitor(kbUuid);
  return (
    queryClient.getQueryData<ProcessingEventsPage>([...monitorKey, "events", TENANT_MONITOR_EVENTS_PARAMS]) ??
    queryClient.getQueryData<ProcessingEventsPage>([...monitorKey, "events", {}])
  );
}

function useMonitorPollOptions(kbUuid: string | undefined, scope?: MonitorScope) {
  const queryClient = useQueryClient();

  return useMemo(() => {
    if (!kbUuid) {
      return { refetchInterval: false as const, refetchIntervalInBackground: false };
    }

    const resolvePollInterval = (): number | false => {
      const monitorKey = queryKeys.kbProcessingMonitor(kbUuid);
      const runs = queryClient.getQueryData<{ items: IngestRun[] }>([...monitorKey, "ingest-runs"]);
      const tenantEvents = readTenantEventsFromCache(queryClient, kbUuid);
      const scopedParams = scope?.trainingItemId ? { training_item_id: scope.trainingItemId } : null;
      const scopedEvents = scopedParams
        ? queryClient.getQueryData<ProcessingEventsPage>([...monitorKey, "events", scopedParams])
        : undefined;

      return computeMonitorPollInterval(
        runs?.items,
        scopedEvents?.items ?? tenantEvents?.items,
        scope?.trainingItemId,
        tenantEvents?.items,
      );
    };

    return {
      refetchInterval: resolvePollInterval,
      refetchIntervalInBackground: true,
      staleTime: 0,
      refetchOnMount: "always" as const,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    };
  }, [kbUuid, queryClient, scope?.trainingItemId]);
}

export function useProcessingMonitorBundle(kbUuid: string | undefined, scope?: MonitorScope) {
  const pollOptions = useMonitorPollOptions(kbUuid, scope);
  const scopedEventsParams = scope?.trainingItemId ? { training_item_id: scope.trainingItemId } : undefined;
  const issuesParams = scope?.trainingItemId
    ? { training_item_id: scope.trainingItemId, status: "OPEN" }
    : undefined;

  const runsQuery = useMonitorIngestRuns(kbUuid, pollOptions);
  const tenantEventsQuery = useProcessingEvents(
    kbUuid,
    TENANT_MONITOR_EVENTS_PARAMS,
    scope?.trainingItemId ? pollOptions : { enabled: false },
  );
  const eventsQuery = useProcessingEvents(
    kbUuid,
    scope?.trainingItemId ? scopedEventsParams : TENANT_MONITOR_EVENTS_PARAMS,
    pollOptions,
  );
  const issuesQuery = useProcessingIssues(kbUuid, issuesParams, pollOptions);
  const metricsQuery = useProcessingMetrics(kbUuid, pollOptions);
  const understandingQuery = useUnderstandingStatus(
    kbUuid,
    scope?.trainingItemId,
    scope?.trainingItemId ? pollOptions : undefined,
  );

  const tenantEvents = tenantEventsQuery.data?.items ?? eventsQuery.data?.items;
  const pollInterval = computeMonitorPollInterval(
    runsQuery.data?.items,
    eventsQuery.data?.items,
    scope?.trainingItemId,
    tenantEvents,
  );

  return {
    runsQuery,
    eventsQuery,
    tenantEventsQuery,
    referenceEventsQuery: tenantEventsQuery,
    issuesQuery,
    metricsQuery,
    understandingQuery,
    isLive: pollInterval !== false,
    pollInterval,
  };
}
