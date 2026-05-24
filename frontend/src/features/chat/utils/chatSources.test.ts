import { describe, expect, it } from "vitest";

import { dedupeChatSources, getEncodedHistoryText, shouldShowAnswerSources } from "./chatSources";

describe("shouldShowAnswerSources", () => {
  it("shows explicit sources", () => {
    expect(shouldShowAnswerSources({ answer: "ok" }, "ok", "insufficient", 1)).toBe(true);
  });

  it("hides no-answer and fallback answers without sources", () => {
    expect(shouldShowAnswerSources({ answer: "", answer_mode: "no_answer" }, "insufficient", "insufficient", 0)).toBe(false);
    expect(shouldShowAnswerSources({ answer: "ok", answer_source: "llm_fallback" }, "ok", "insufficient", 0)).toBe(false);
  });

  it("shows grounded answers without explicit source array when source mode allows it", () => {
    expect(shouldShowAnswerSources({ answer: "ok", answer_mode: "answer", answer_source: "knowledge" }, "ok", "insufficient", 0)).toBe(true);
  });

  it("deduplicates chat text training sources by snippet", () => {
    expect(
      dedupeChatSources([
        { kb_uuid: "kb", point_id: "1", title: "Chatből tanított szöveg", snippet: "same", source_type: "text" },
        { kb_uuid: "kb", point_id: "2", title: "Chatből tanított szöveg", snippet: "same", source_type: "text" },
      ])
    ).toHaveLength(1);
  });

  it("extracts encoded history text from prompt context", () => {
    expect(
      getEncodedHistoryText({ answer: "answer", prompt_context: { encoded_answer_text: "encoded" } }, "encoded_answer_text", "fallback")
    ).toBe("encoded");
    expect(getEncodedHistoryText({ answer: "answer" }, "encoded_answer_text", "fallback")).toBe("fallback");
  });
});
