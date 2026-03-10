import { describe, expect, it } from "vitest";

import { toCompactNumber, toCurrency, toPercent } from "@/lib/format";

describe("format helpers", () => {
  it("formats percentages safely", () => {
    expect(toPercent(0.42)).toBe("42.0%");
    expect(toPercent(null)).toBe("-");
    expect(toPercent(undefined)).toBe("-");
  });

  it("formats compact numbers", () => {
    expect(toCompactNumber(12000)).toBeTruthy();
  });

  it("formats currency in INR", () => {
    expect(toCurrency(1250000)).toContain("₹");
  });
});
