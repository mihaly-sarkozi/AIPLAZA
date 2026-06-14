import { describe, expect, it } from "vitest";

import type { ProcessingEventSummary } from "../../../api/services/kb/kbProcessingApi";
import { computeMonitorPollInterval, PROCESSING_MONITOR_POLL_MS } from "./processingMonitorPolling";

function runningEvent(itemId: string): ProcessingEventSummary {
  return {
    id: `evt-${itemId}`,
    knowledge_base_id: "kb",
    training_item_id: itemId,
    module: "kb_understanding",
    stage: "EXTRACT",
    step: "EXTRACT_CONTENT",
    event_type: "EXTRACT_STARTED",
    status: "started",
    input_summary_json: {},
    output_summary_json: {},
    metadata_json: {},
    created_at: "2026-06-14T12:00:00Z",
  };
}

describe("computeMonitorPollInterval", () => {
  it("polls tenant list while any flow is running", () => {
    expect(
      computeMonitorPollInterval([], [runningEvent("item-a"), runningEvent("item-b")]),
    ).toBe(PROCESSING_MONITOR_POLL_MS);
  });

  it("polls scoped detail from tenant cache when item flow is running", () => {
    const tenantEvents = [runningEvent("item-a")];
    expect(computeMonitorPollInterval([], [], "item-a", tenantEvents)).toBe(PROCESSING_MONITOR_POLL_MS);
  });

  it("polls scoped detail while ingest runs exist but item events not loaded yet", () => {
    expect(
      computeMonitorPollInterval([{ id: "run-1", status: "completed", items: [{ id: "item-a" }] } as never], [], "item-a"),
    ).toBe(PROCESSING_MONITOR_POLL_MS);
  });

  it("stops polling when nothing is active", () => {
    expect(computeMonitorPollInterval([], [])).toBe(false);
  });
});
