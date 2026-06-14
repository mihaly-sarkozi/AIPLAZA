import { describe, expect, it } from "vitest";

import { buildStepSummaryDisplay } from "./stepSummaryDisplay";

const t = (key: string) => {
  const map: Record<string, string> = {
    "kb.processingMonitor.languages.hu": "Magyar",
    "kb.processingMonitor.languages.mixed": "Vegyes",
    "kb.processingMonitor.languages.unknown": "Ismeretlen",
    "kb.processingMonitor.entityTypes.company": "Cég",
    "kb.processingMonitor.entityTypes.person": "Személy",
    "kb.processingMonitor.chunkTypes.text": "Szöveg",
    "kb.processingMonitor.partTypes.TEXT": "Szöveg",
    "kb.processingMonitor.blockTable.page": "Oldal",
    "kb.processingMonitor.blockTable.tokens": "Token",
    "kb.processingMonitor.blockTable.chars": "Karakter",
  };
  return map[key] ?? key;
};

describe("buildStepSummaryDisplay", () => {
  it("formats language detection output with percent and distribution", () => {
    const display = buildStepSummaryDisplay(
      "DETECT_LANGUAGE",
      {
        chunks_checked: 107,
        document_language_code: "hu",
        document_language_confidence: 0.9658,
        language_distribution: { hu: 86, mixed: 4, unknown: 17 },
      },
      "output",
      t,
      "hu-HU",
    );

    expect(display.rows.find((row) => row.key === "document_language_confidence")?.value).toBe("96,6%");
    expect(display.rows.find((row) => row.key === "language_distribution")?.value).toContain("Magyar: 86");
    expect(display.previewTables).toHaveLength(0);
  });

  it("shows entity preview table for entity extraction", () => {
    const display = buildStepSummaryDisplay(
      "EXTRACT_ENTITIES",
      {
        entity_count: 2,
        mention_count: 3,
        entities: [
          { name: "Acme Kft.", type: "company", confidence: 0.92 },
          { name: "Kovács János", type: "person", confidence: 0.81 },
        ],
      },
      "output",
      t,
      "hu-HU",
    );

    expect(display.rows).toHaveLength(2);
    expect(display.previewTables[0]?.rows[0]).toEqual({
      name: "Acme Kft.",
      type: "Cég",
      confidence: "92%",
    });
  });

  it("shows chunk preview table for build chunks step", () => {
    const display = buildStepSummaryDisplay(
      "BUILD_CHUNKS",
      {
        chunks_created: 2,
        chunks: [
          { index: 1, chunk_type: "text", page: 1, tokens: 42, snippet: "Első tudásdarab szöveg." },
        ],
      },
      "output",
      t,
      "hu-HU",
    );

    expect(display.previewTables[0]?.id).toBe("chunks");
    expect(display.previewTables[0]?.rows[0]?.snippet).toContain("Első tudásdarab");
  });
});
