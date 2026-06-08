import { describe, expect, it } from "vitest";

import {
  buildTrainingSuccessDetail,
  combineTrainingProgress,
  resolveTrainingCharCount,
  estimateFileCharactersForProgress,
  estimatedTrainingProgress,
  exactTrainingCharCount,
  isDuplicateOnlyTrainingRun,
} from "./chatTraining";

describe("chatTraining helpers", () => {
  it("prefers total character count metadata", () => {
    expect(exactTrainingCharCount({ metadata: { total_char_count: 42 }, items: [{ metadata: { char_count: 10 } }] })).toBe(42);
  });

  it("falls back to item character counts", () => {
    expect(exactTrainingCharCount({ items: [{ metadata: { char_count: 10 } }, { metadata: { char_count: 7 } }] })).toBe(17);
  });

  it("detects duplicate-only runs", () => {
    expect(isDuplicateOnlyTrainingRun({ items: [{ status: "duplicate" }, { status: "duplicate" }] })).toBe(true);
    expect(isDuplicateOnlyTrainingRun({ duplicate_count: 2, completed_count: 0 })).toBe(true);
    expect(isDuplicateOnlyTrainingRun({ items: [{ status: "completed" }] })).toBe(false);
  });

  it("estimates file characters by file type", () => {
    expect(estimateFileCharactersForProgress(new File(["abcd"], "notes.txt"))).toBeGreaterThan(1);
    expect(estimateFileCharactersForProgress(new File(["abcd"], "doc.pdf"))).toBeGreaterThan(0);
  });

  it("keeps visual progress below completion unless actual progress completes", () => {
    expect(combineTrainingProgress(0, 80)).toBe(80);
    expect(combineTrainingProgress(30, 80)).toBe(80);
    expect(combineTrainingProgress(100, 80)).toBe(100);
  });

  it("falls back to stored character count when run payload has no items", () => {
    expect(resolveTrainingCharCount({ items: [] }, 89002)).toBe(89002);
    expect(resolveTrainingCharCount({ items: [{ metadata: { char_count: 120 } }] }, 89002)).toBe(120);
  });

  it("builds success detail with character count", () => {
    const t = (key: string) =>
      (
        {
          "chat.trainingCompletedPercent": "Tanítás 100%",
          "chat.fileCharacterCount": "{{count}} karakter.",
        } as Record<string, string>
      )[key] ?? key;

    expect(buildTrainingSuccessDetail(89002, "hu-HU", t)).toContain("Tanítás 100%");
    expect(buildTrainingSuccessDetail(89002, "hu-HU", t)).toContain("karakter.");
    expect(buildTrainingSuccessDetail(89002, "hu-HU", t)).toMatch(/89[\s\u00a0]?002/);
    expect(buildTrainingSuccessDetail(0, "hu-HU", t)).toBe("Tanítás 100%");
  });

  it("estimates progress in a bounded range", () => {
    expect(estimatedTrainingProgress(0, 1000)).toBeGreaterThanOrEqual(6);
    expect(estimatedTrainingProgress(2000, 1000)).toBeLessThanOrEqual(99);
  });
});
