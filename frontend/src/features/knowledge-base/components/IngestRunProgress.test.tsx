import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import IngestRunProgress from "./IngestRunProgress";

type IngestRunProgressProps = React.ComponentProps<typeof IngestRunProgress>;

const run: IngestRunProgressProps["run"] = {
  id: "run-1",
  corpus_uuid: "kb-1",
  status: "running",
  input_channel: "chat",
  pipeline_route: "standard",
  batch_size: 2,
  queued_count: 1,
  processing_count: 1,
  completed_count: 1,
  failed_count: 0,
  duplicate_count: 0,
  rejected_count: 0,
  continue_on_error: true,
  created_at: "2026-01-01T10:00:00Z",
  updated_at: "2026-01-01T10:01:00Z",
  created_by_label: "Owner",
  items: [],
  events: [],
  metadata: {
    total_char_count: 1234,
    total_sentence_count: 12,
    progress_summary: {
      overall_percent: 50,
      label: "Félig kész",
      terminal_items: 1,
      total_items: 2,
      active_item_label: "doc.txt",
      active_module_label: "Parser",
    },
  },
};

describe("IngestRunProgress", () => {
  it("megjeleníti a run fő adatait és progress értékét", () => {
    render(<IngestRunProgress run={run} selectedItem={null} kb={{ name: "Smoke KB" }} parserErrorMessage="" />);

    expect(screen.getByText("Run folyamat")).toBeInTheDocument();
    expect(screen.getByText("Smoke KB")).toBeInTheDocument();
    expect(screen.getAllByText("run-1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("50%").length).toBeGreaterThan(0);
  });

  it("parser hiba esetén hibablokkot jelenít meg", () => {
    render(<IngestRunProgress run={run} selectedItem={null} kb={{ name: "Smoke KB" }} parserErrorMessage="Parser failed" />);

    expect(screen.getByText("Parser hiba")).toBeInTheDocument();
    expect(screen.getAllByText("Parser failed").length).toBeGreaterThan(0);
  });
});
