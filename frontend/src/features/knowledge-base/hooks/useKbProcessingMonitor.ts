import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import {
  getProcessingMetrics,
  getUnderstandingStatus,
  listProcessingEvents,
  listProcessingIssues,
  type ProcessingEventsPage,
  type ProcessingIssuesPage,
  type ProcessingMetricsResponse,
  type UnderstandingStatusResponse,
} from "../../../api/services/kb/kbProcessingApi";
import { listIngestRuns } from "../../../api/services/kb/kbIngestApi";
import { queryKeys } from "../../../queryKeys";

export function useProcessingMetrics(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<ProcessingMetricsResponse | null>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kbProcessingMonitor(kbUuid ?? ""), "metrics"],
    queryFn: () => getProcessingMetrics(kbUuid!),
    enabled: Boolean(kbUuid),
    ...options,
  });
}

export function useProcessingEvents(
  kbUuid: string | undefined,
  params?: { training_item_id?: string; limit?: number },
  options?: Omit<UseQueryOptions<ProcessingEventsPage>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kbProcessingMonitor(kbUuid ?? ""), "events", params ?? {}],
    queryFn: () =>
      listProcessingEvents(kbUuid!, {
        training_item_id: params?.training_item_id,
        limit: params?.limit ?? (params?.training_item_id ? 200 : 500),
        offset: 0,
      }),
    enabled: Boolean(kbUuid),
    ...options,
  });
}

export function useProcessingIssues(
  kbUuid: string | undefined,
  params?: { training_item_id?: string; status?: string },
  options?: Omit<UseQueryOptions<ProcessingIssuesPage>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kbProcessingMonitor(kbUuid ?? ""), "issues", params ?? {}],
    queryFn: () =>
      listProcessingIssues(kbUuid!, {
        training_item_id: params?.training_item_id,
        status: params?.status,
        limit: params?.training_item_id ? 100 : 300,
        offset: 0,
      }),
    enabled: Boolean(kbUuid),
    ...options,
  });
}

export function useUnderstandingStatus(
  kbUuid: string | undefined,
  itemId: string | undefined,
  options?: Omit<UseQueryOptions<UnderstandingStatusResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kbProcessingMonitor(kbUuid ?? ""), "understanding", itemId ?? ""],
    queryFn: () => getUnderstandingStatus(kbUuid!, itemId!),
    enabled: Boolean(kbUuid && itemId),
    ...options,
  });
}

export function useMonitorIngestRuns(
  kbUuid: string | undefined,
  options?: Omit<UseQueryOptions<Awaited<ReturnType<typeof listIngestRuns>>>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...queryKeys.kbProcessingMonitor(kbUuid ?? ""), "ingest-runs"],
    queryFn: () => listIngestRuns(kbUuid!, { limit: 100, offset: 0 }),
    enabled: Boolean(kbUuid),
    ...options,
  });
}
