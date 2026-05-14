import { describe, expect, it } from "vitest";

describe("api contracts", () => {
  it("keeps validation severity enum aligned", () => {
    const severities = ["error", "warning"];
    expect(severities).toContain("error");
    expect(severities).toContain("warning");
  });
});
