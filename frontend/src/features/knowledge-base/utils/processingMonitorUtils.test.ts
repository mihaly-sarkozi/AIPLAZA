import { describe, expect, it } from "vitest";

import type { ProcessingEventSummary, ProcessingIssueSummary } from "../../../api/services/kb/kbProcessingApi";
import {
  countOpenBlockingIssues,
  deriveFlowStatus,
  isOpenBlockingIssue,
} from "./processingMonitorUtils";

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
});
