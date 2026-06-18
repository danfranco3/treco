import { estimateCost, formatCost, formatTokens } from "../lib/cost";

describe("estimateCost", () => {
  it("returns 0 for zero tokens", () => {
    expect(estimateCost(0, 0, null)).toBe(0);
  });

  it("uses default pricing for null model", () => {
    // _default: input $3.00/M, output $15.00/M
    const cost = estimateCost(1_000_000, 0, null);
    expect(cost).toBeCloseTo(3.0);
  });

  it("uses default pricing for unknown model", () => {
    const cost = estimateCost(1_000_000, 0, "gpt-unknown-99");
    expect(cost).toBeCloseTo(3.0);
  });

  it("uses correct rates for haiku", () => {
    // haiku: input $0.80/M, output $4.00/M
    const cost = estimateCost(1_000_000, 0, "claude-haiku-4-5-20251001");
    expect(cost).toBeCloseTo(0.8);
  });

  it("uses correct rates for sonnet", () => {
    // sonnet-4-6: input $3.00/M, output $15.00/M
    const cost = estimateCost(0, 1_000_000, "claude-sonnet-4-6");
    expect(cost).toBeCloseTo(15.0);
  });

  it("uses correct rates for opus", () => {
    // opus-4-8: input $15.00/M, output $75.00/M
    const cost = estimateCost(1_000_000, 1_000_000, "claude-opus-4-8");
    expect(cost).toBeCloseTo(90.0);
  });

  it("uses correct rates for gpt-4o-mini", () => {
    // gpt-4o-mini: input $0.15/M, output $0.60/M
    const cost = estimateCost(1_000_000, 0, "gpt-4o-mini");
    expect(cost).toBeCloseTo(0.15);
  });

  it("combines input and output correctly", () => {
    // haiku: 500k in + 500k out
    const cost = estimateCost(500_000, 500_000, "claude-haiku-4-5-20251001");
    expect(cost).toBeCloseTo(0.4 + 2.0); // 0.5 * 0.8 + 0.5 * 4.0
  });

  it("is proportional to token count", () => {
    const half = estimateCost(500_000, 0, null);
    const full = estimateCost(1_000_000, 0, null);
    expect(full).toBeCloseTo(half * 2);
  });
});

describe("formatCost", () => {
  it("shows $0.00 for negligible cost", () => {
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(0.0001)).toBe("$0.00");
  });

  it("shows 4 decimal places for tiny costs", () => {
    const result = formatCost(0.005);
    expect(result).toMatch(/^\$0\.\d{4}$/);
  });

  it("shows 3 decimal places for normal costs", () => {
    const result = formatCost(0.123);
    expect(result).toBe("$0.123");
  });

  it("shows 3 decimal places for large costs", () => {
    const result = formatCost(12.5);
    expect(result).toBe("$12.500");
  });

  it("formats exactly $0.01", () => {
    expect(formatCost(0.01)).toBe("$0.010");
  });
});

describe("formatTokens", () => {
  it("formats with thousands separator", () => {
    const result = formatTokens(1_000_000);
    expect(result).toMatch(/1[,.]000[,.]000/);
  });

  it("formats small number without separator", () => {
    const result = formatTokens(500);
    expect(result).toContain("500");
  });

  it("handles zero", () => {
    expect(formatTokens(0)).toBe("0");
  });
});
