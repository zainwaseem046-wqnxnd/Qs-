import { formatMoney, formatMoneyCompact, formatPercent, isDecimalString, parseMoneyInput } from "./money";

describe("formatMoney", () => {
  it("formats decimal strings exactly without floating point", () => {
    expect(formatMoney("12500000.00")).toBe("$12,500,000.00");
    expect(formatMoney("0.1")).toBe("$0.10");
    expect(formatMoney("99999999999999999.99")).toBe("$99,999,999,999,999,999.99");
  });
  it("rounds half-up for display", () => {
    expect(formatMoney("2.345")).toBe("$2.35");
    expect(formatMoney("1999.995")).toBe("$2,000.00");
    expect(formatMoney("1234.5", "USD", { cents: false })).toBe("$1,235");
  });
  it("shows negatives in accounting parentheses", () => {
    expect(formatMoney("-1500.25")).toBe("($1,500.25)");
    expect(formatMoney("-0.001")).toBe("$0.00");
  });
  it("renders a dash for missing or invalid values", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney("abc")).toBe("—");
  });
  it("uses currency symbols", () => {
    expect(formatMoney("10", "CAD")).toBe("CA$10.00");
  });
});

describe("formatMoneyCompact", () => {
  it.each([
    ["12500000.00", "$12.5M"],
    ["940000", "$940K"],
    ["1250000000", "$1.25B"],
    ["999", "$999"],
    ["11234568.19", "$11.2M"],
    ["999950000", "$1,000M"],
  ])("%s -> %s", (input, out) => expect(formatMoneyCompact(input)).toBe(out));
});

describe("parseMoneyInput", () => {
  it("normalises typed amounts", () => {
    expect(parseMoneyInput("$1,250,000.5")).toBe("1250000.50");
    expect(parseMoneyInput("007")).toBe("7.00");
  });
  it("rejects invalid input instead of guessing", () => {
    expect(parseMoneyInput("12.345")).toBeNull();
    expect(parseMoneyInput("-5")).toBeNull();
    expect(parseMoneyInput("1e6")).toBeNull();
    expect(parseMoneyInput("")).toBeNull();
  });
});

describe("helpers", () => {
  it("formatPercent", () => {
    expect(formatPercent("10.00")).toBe("10%");
    expect(formatPercent("5.25")).toBe("5.25%");
  });
  it("isDecimalString", () => {
    expect(isDecimalString("1.00")).toBe(true);
    expect(isDecimalString("1,000")).toBe(false);
  });
});
