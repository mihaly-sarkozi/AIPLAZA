import type { ProcessingEventSummary } from "../../../api/services/kb/kbProcessingApi";
import type { IngestRun } from "../../../api/services/kb/types";
import { isTrainingActive } from "./trainingProgress";
import { deriveFlowStatus, type ProcessingFlowStatus } from "./processingMonitorUtils";

export const PROCESSING_MONITOR_POLL_MS = 2000;

export function isActiveFlowStatus(status: ProcessingFlowStatus): boolean {
  return status === "running";
}

export function computeMonitorPollInterval(
  runs: IngestRun[] | undefined,
  events: ProcessingEventSummary[] | undefined,
  trainingItemId?: string,
): number | false {
  const runList = runs ?? [];
  if (runList.some((run) => isTrainingActive(run.status))) {
    return PROCESSING_MONITOR_POLL_MS;
  }

  const eventList = events ?? [];
  if (!eventList.length) {
    return false;
  }

  if (trainingItemId) {
    const itemEvents = eventList.filter((event) => event.training_item_id === trainingItemId);
    if (itemEvents.length && deriveFlowStatus(itemEvents, []) === "running") {
      return PROCESSING_MONITOR_POLL_MS;
    }
    return false;
  }

  const itemIds = new Set(
    eventList.map((event) => event.training_item_id).filter((id): id is string => Boolean(id)),
  );
  for (const itemId of itemIds) {
    const itemEvents = eventList.filter((event) => event.training_item_id === itemId);
    if (deriveFlowStatus(itemEvents, []) === "running") {
      return PROCESSING_MONITOR_POLL_MS;
    }
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
    if (event.training_item_id) itemIds.add(event.training_item_id);
  }

  let active = 0;
  for (const itemId of itemIds) {
    const itemEvents = events.filter((event) => event.training_item_id === itemId);
    if (deriveFlowStatus(itemEvents, []) === "running") {
      active += 1;
    }
  }
  if (runs.some((run) => isTrainingActive(run.status)) && active === 0) {
    return 1;
  }
  return active;
}
