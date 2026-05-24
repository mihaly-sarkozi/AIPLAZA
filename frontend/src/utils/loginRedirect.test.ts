import { describe, expect, it } from "vitest";

import { getSafeLoginRedirect } from "./loginRedirect";

describe("getSafeLoginRedirect", () => {
  it("allows internal allowlisted paths", () => {
    expect(getSafeLoginRedirect("/chat")).toBe("/chat");
    expect(getSafeLoginRedirect("/kb/demo")).toBe("/kb/demo");
    expect(getSafeLoginRedirect("/admin/users")).toBe("/admin/users");
    expect(getSafeLoginRedirect("/settings/profile")).toBe("/settings/profile");
  });

  it("rejects external https URLs", () => {
    expect(getSafeLoginRedirect("https://evil.example/login")).toBe("/chat");
  });

  it("rejects protocol-relative URLs", () => {
    expect(getSafeLoginRedirect("//evil.com")).toBe("/chat");
  });

  it("rejects javascript and data URLs", () => {
    expect(getSafeLoginRedirect("javascript:alert(1)")).toBe("/chat");
    expect(getSafeLoginRedirect("data:text/html,<script>alert(1)</script>")).toBe("/chat");
  });

  it("rejects control characters", () => {
    expect(getSafeLoginRedirect("/chat%0A//evil.com")).toBe("/chat");
    expect(getSafeLoginRedirect("/kb/demo%0D")).toBe("/chat");
  });

  it("rejects non-allowlisted paths", () => {
    expect(getSafeLoginRedirect("/billing")).toBe("/chat");
    expect(getSafeLoginRedirect("/platform-admin")).toBe("/chat");
  });

  it("falls back for empty redirects", () => {
    expect(getSafeLoginRedirect("")).toBe("/chat");
    expect(getSafeLoginRedirect(null)).toBe("/chat");
    expect(getSafeLoginRedirect(undefined)).toBe("/chat");
  });
});
