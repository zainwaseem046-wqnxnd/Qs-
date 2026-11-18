import { formatDate } from "./hooks";
import { formatMoney } from "./money";
import { setRegion, terms } from "./region";

afterEach(() => setRegion("US"));

describe("region conventions", () => {
  it("formats calendar dates per organization country", () => {
    setRegion("US");
    expect(formatDate("2027-06-30")).toBe("06/30/2027");
    setRegion("GB");
    expect(formatDate("2027-06-30")).toBe("30/06/2027");
  });
  it("uses UK terminology and postcode rules", () => {
    const uk = terms("GB");
    expect(uk.postalLabel).toBe("Postcode");
    expect(uk.retainage).toBe("Retention");
    expect(uk.usesStates).toBe(false);
    expect(uk.postalPattern.test("SW1A 1AA")).toBe(true);
    expect(uk.postalPattern.test("78701")).toBe(false);
    expect(terms("US").postalPattern.test("78701-1234")).toBe(true);
  });
  it("formats sterling", () => {
    expect(formatMoney("4250000.5", "GBP")).toBe("£4,250,000.50");
  });
});
