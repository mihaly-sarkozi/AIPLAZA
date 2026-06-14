import { describe, expect, it } from "vitest";

import type { ProcessingEventSummary, ProcessingIssueSummary } from "../../../api/services/kb/kbProcessingApi";
import {
  countOpenBlockingIssues,
  deriveFlowProgress,
  deriveFlowStatus,
  isOpenBlockingIssue,
} from "./processingMonitorUtils";

function understandingExtractCompleted(): ProcessingEventSummary {
  return {
    id: "u1",
    knowledge_base_id: "kb",
    training_item_id: "training_item_1",
    module: "kb_understanding",
    stage: "EXTRACT",
    step: "EXTRACT_CONTENT",
    event_type: "EXTRACT_COMPLETED",
    status: "completed",
    input_summary_json: {},
    output_summary_json: {},
    metadata_json: {},
    created_at: "2026-06-14T10:00:00Z",
  };
}

function understandingNormalizeStarted(): ProcessingEventSummary {
  return {
    id: "u2",
    knowledge_base_id: "kb",
    training_item_id: "training_item_1",
    module: "kb_understanding",
    stage: "NORMALIZE",
    step: "NORMALIZE_PARTS",
    event_type: "NORMALIZE_STARTED",
    status: "started",
    input_summary_json: {},
    output_summary_json: {},
    metadata_json: {},
    created_at: "2026-06-14T10:01:00Z",
  };
}

function indexingCompletedEvent(): ProcessingEventSummary {
  return {
    id: "1",
    knowledge_base_id: "kb",
    module: "kb_indexing",
    stage: "INDEXING",
    step: "PIPELINE",
    event_type: "INDEXING_COMPLETED",
    status: "completed",
    input_summary_json: {},
    output_summary_json: {},
    metadata_json: {},
    created_at: "2026-06-14T10:00:00Z",
  };
}

function warningIssue(): ProcessingIssueSummary {
  return {
    id: "issue-1",
    knowledge_base_id: "kb",
    module: "kb_discovery",
    stage: "LOCAL_KNOWLEDGE_ENRICHMENT",
    severity: "WARNING",
    issue_code: "NO_TOPICS_DETECTED",
    status: "OPEN",
    first_seen_at: "2026-06-14T10:00:00Z",
    last_seen_at: "2026-06-14T10:00:00Z",
    occurrence_count: 1,
    metadata_json: {},
  };
}

describe("deriveFlowStatus", () => {
  it("marks indexed flows completed even with open warnings", () => {
    expect(deriveFlowStatus([indexingCompletedEvent()], [warningIssue()])).toBe("completed");
  });

  it("counts only blocking issues as open problems", () => {
    expect(isOpenBlockingIssue(warningIssue())).toBe(false);
    expect(countOpenBlockingIssues([warningIssue()])).toBe(0);

    const errorIssue: ProcessingIssueSummary = { ...warningIssue(), id: "issue-2", severity: "ERROR" };
    expect(countOpenBlockingIssues([warningIssue(), errorIssue])).toBe(1);
    expect(deriveFlowStatus([indexingCompletedEvent()], [errorIssue])).toBe("failed");
  });

  it("keeps mid-pipeline flows running after intermediate steps complete", () => {
    const events = [understandingExtractCompleted(), understandingNormalizeStarted()];
    expect(deriveFlowStatus(events, [])).toBe("running");
    expect(deriveFlowProgress(events, [])).not.toBeNull();
  });
});
