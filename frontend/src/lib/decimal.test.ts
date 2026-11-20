import { compareDecimal, decimalError } from "./decimal";

describe("decimal input validation", () => {
  it("enforces decimal places without floats", () => {
    expect(decimalError("125.5", 4)).toBeUndefined();
    expect(decimalError("1,250.25", 2)).toBeUndefined();
    expect(decimalError("1.12345", 4)).toMatch(/4 decimal places/);
    expect(decimalError("-1", 2)).toBeDefined();
    expect(decimalError("1e3", 2)).toBeDefined();
    expect(decimalError("", 2, { required: true, label: "Quantity" })).toBe("Quantity is required");
    expect(decimalError("100.01", 2, { max: "100" })).toBe("Must be at most 100");
    expect(decimalError("100", 2, { max: "100" })).toBeUndefined();
  });
  it("compares exactly", () => {
    expect(compareDecimal("0.1", "0.10")).toBe(0);
    expect(compareDecimal("99999999999999999.99", "99999999999999999.98")).toBe(1);
  });
});
