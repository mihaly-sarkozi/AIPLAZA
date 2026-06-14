import type { ProcessingEventSummary } from "../../../api/services/kb/kbProcessingApi";
import type { IngestRun } from "../../../api/services/kb/types";
import { isTrainingActive } from "./trainingProgress";
import { deriveFlowStatus, resolveFlowItemId, type ProcessingFlowStatus } from "./processingMonitorUtils";

export const PROCESSING_MONITOR_POLL_MS = 1500;

/** Tenant-szintű eseménylista (progress kalibráció + élő poll döntés). */
export const TENANT_MONITOR_EVENTS_PARAMS = { limit: 500 } as const;

export function isActiveFlowStatus(status: ProcessingFlowStatus): boolean {
  return status === "running";
}

function isItemInActiveTrainingRun(runs: IngestRun[], trainingItemId: string): boolean {
  return runs.some(
    (run) =>
      isTrainingActive(run.status) &&
      (run.items ?? []).some((item) => item.id === trainingItemId),
  );
}

function hasAnyActiveFlow(events: ProcessingEventSummary[]): boolean {
  const itemIds = new Set(
    events.map((event) => resolveFlowItemId(event)).filter((id): id is string => Boolean(id)),
  );
  for (const itemId of itemIds) {
    const itemEvents = events.filter((event) => resolveFlowItemId(event) === itemId);
    if (isActiveFlowStatus(deriveFlowStatus(itemEvents, []))) {
      return true;
    }
  }
  return false;
}

function isItemFlowRunning(
  events: ProcessingEventSummary[],
  trainingItemId: string,
): boolean {
  const itemEvents = events.filter((event) => resolveFlowItemId(event) === trainingItemId);
  return itemEvents.length > 0 && isActiveFlowStatus(deriveFlowStatus(itemEvents, []));
}

export function computeMonitorPollInterval(
  runs: IngestRun[] | undefined,
  events: ProcessingEventSummary[] | undefined,
  trainingItemId?: string,
  tenantEvents?: ProcessingEventSummary[] | undefined,
): number | false {
  const runList = runs ?? [];
  const eventList = events ?? [];
  const tenantEventList = tenantEvents ?? eventList;

  if (runList.some((run) => isTrainingActive(run.status))) {
    return PROCESSING_MONITOR_POLL_MS;
  }

  if (trainingItemId) {
    if (isItemInActiveTrainingRun(runList, trainingItemId)) {
      return PROCESSING_MONITOR_POLL_MS;
    }
    if (isItemFlowRunning(eventList, trainingItemId)) {
      return PROCESSING_MONITOR_POLL_MS;
    }
    if (isItemFlowRunning(tenantEventList, trainingItemId)) {
      return PROCESSING_MONITOR_POLL_MS;
    }
    if (hasAnyActiveFlow(tenantEventList)) {
      return PROCESSING_MONITOR_POLL_MS;
    }
    if (!eventList.length && runList.length > 0) {
      return PROCESSING_MONITOR_POLL_MS;
    }
    return false;
  }

  if (!tenantEventList.length && !eventList.length) {
    return false;
  }

  if (hasAnyActiveFlow(tenantEventList) || hasAnyActiveFlow(eventList)) {
    return PROCESSING_MONITOR_POLL_MS;
  }
  return false;
}

export function countActiveFlows(
  runs: IngestRun[],
  events: ProcessingEventSummary[],
): number {
  const itemIds = new Set<string>();
  for (const run of runs) {
    for (const item of run.items ?? []) {
      if (item.id) itemIds.add(item.id);
    }
  }
  for (const event of events) {
    const itemId = resolveFlowItemId(event);
    if (itemId) itemIds.add(itemId);
  }

  let active = 0;
  for (const itemId of itemIds) {
    const itemEvents = events.filter((event) => resolveFlowItemId(event) === itemId);
    if (deriveFlowStatus(itemEvents, []) === "running") {
      active += 1;
    }
  }
  if (runs.some((run) => isTrainingActive(run.status)) && active === 0) {
    return 1;
  }
  return active;
}
