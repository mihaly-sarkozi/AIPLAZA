import { describe, expect, it } from "vitest";

import { sanitizeMessage } from "./sanitize";

describe("sanitizeMessage", () => {
  it("removes script tags", () => {
    expect(sanitizeMessage("hello<script>alert(1)</script>world")).toBe("helloworld");
  });

  it("removes img event handlers", () => {
    expect(sanitizeMessage('x<img src="x" onerror="alert(1)">y')).toBe("xy");
  });

  it("removes HTML tags", () => {
    expect(sanitizeMessage("<strong>Hello</strong> <em>world</em>")).toBe("Hello world");
  });

  it("keeps plain text", () => {
    expect(sanitizeMessage("Sima szoveg 123.")).toBe("Sima szoveg 123.");
  });

  it("handles empty and non-string input safely", () => {
    expect(sanitizeMessage("")).toBe("");
    expect(sanitizeMessage(null as unknown as string)).toBe("");
    expect(sanitizeMessage(undefined as unknown as string)).toBe("");
  });
});
