import { describe, expect, it } from "vitest";

import {
  claimTextForBlockClaim,
  formatSplitConfidence,
  getBlockTypeLabel,
  getInformationValueBadgeClass,
  getParagraphDebugDetails,
  getParagraphRoleSummary,
  getSentenceRefinementSummary,
  getSentenceSplitSummary,
} from "./ingestDetailHelpers";
import type { ParagraphRow } from "./ingestDetailTypes";
import type { IngestRunTraceClaim } from "../services";

const paragraph = (metadata: Record<string, unknown>): ParagraphRow => ({
  id: "p1",
  source_id: "s1",
  document_id: "d1",
  order_index: 1,
  text_content: "text",
  char_start: 0,
  char_end: 4,
  sentence_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  metadata,
});

describe("ingestDetailHelpers", () => {
  it("labels block types and paragraph roles", () => {
    expect(getBlockTypeLabel("heading")).toBe("Header / title");
    expect(getBlockTypeLabel("custom")).toBe("custom");
    expect(getParagraphRoleSummary(paragraph({ block_type: "table_row", table_role: "header" }))).toBe("Táblafejléc");
    expect(getParagraphRoleSummary(paragraph({ block_type: "list_item" }))).toBe("Lista egység");
  });

  it("builds paragraph debug details from table metadata", () => {
    expect(
      getParagraphDebugDetails(
        paragraph({
          line_count: 2,
          table_column_headers: ["A", "B"],
          table_cells: ["1", "2"],
          docx_table_row_index: 0,
        })
      )
    ).toContain("oszlopok: A | B");
  });

  it("summarizes sentence split and refinement metadata", () => {
    expect(getSentenceSplitSummary({ split_reason: "strong_punctuation", split_strength: "strong", uncertain_split: false })).toBe(
      "Erős mondatzárás | erő: Erős | stabil"
    );
    expect(getSentenceRefinementSummary({ claim_split_reasons: ["subject"], subject_hint: "ACME" })).toBe("claim okok: subject | S: ACME");
  });

  it("formats confidence and claim fallback text", () => {
    const claim = {
      subject_text: "A",
      predicate: "is",
      object_text: "B",
    } as IngestRunTraceClaim;
    expect(formatSplitConfidence(0.83)).toBe("83%");
    expect(claimTextForBlockClaim(claim, "fallback")).toBe("A is B");
    expect(claimTextForBlockClaim(undefined, "fallback")).toBe("fallback");
  });

  it("returns stable information value badge classes", () => {
    expect(getInformationValueBadgeClass("strong")).toContain("emerald");
    expect(getInformationValueBadgeClass("discard_candidate")).toContain("rose");
    expect(getInformationValueBadgeClass("unknown")).toContain("slate");
  });
});
