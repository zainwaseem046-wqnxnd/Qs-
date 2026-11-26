/**
 * Country-specific presentation (United States vs United Kingdom). Set once from the active organization
 * so plain formatting helpers (dates) follow the organization's conventions.
 */

export type CountryCode = "US" | "GB";

export interface RegionTerms {
  locale: string;
  postalLabel: string;
  postalPlaceholder: string;
  postalPattern: RegExp;
  postalError: string;
  usesStates: boolean;
  retainage: string;
  dateHint: string;
  labour: string;
  equipment: string;
  payApp: string;
  payApps: string;
  markupPresets: { name: string; percent: string; basis: "direct_cost" | "cumulative"; include_in_budget: boolean }[];
}

const TERMS: Record<CountryCode, RegionTerms> = {
  US: {
    locale: "en-US",
    postalLabel: "ZIP code",
    postalPlaceholder: "78701",
    postalPattern: /^(\d{5}(-\d{4})?)?$/,
    postalError: "Use a 5-digit or ZIP+4 code",
    usesStates: true,
    retainage: "Retainage",
    dateHint: "MM/DD/YYYY",
    labour: "Labor",
    equipment: "Equipment",
    payApp: "Pay application",
    payApps: "Pay applications",
    markupPresets: [
      { name: "General conditions", percent: "8", basis: "direct_cost", include_in_budget: true },
      { name: "Contingency", percent: "5", basis: "cumulative", include_in_budget: true },
      { name: "Insurance & bonds", percent: "1.5", basis: "cumulative", include_in_budget: true },
      { name: "Fee", percent: "4", basis: "cumulative", include_in_budget: false },
    ],
  },
  GB: {
    locale: "en-GB",
    postalLabel: "Postcode",
    postalPlaceholder: "SW1A 1AA",
    postalPattern: /^([A-Za-z]{1,2}\d[A-Za-z\d]? ?\d[A-Za-z]{2})?$/,
    postalError: "Enter a valid UK postcode, e.g. SW1A 1AA",
    usesStates: false,
    retainage: "Retention",
    dateHint: "DD/MM/YYYY",
    labour: "Labour",
    equipment: "Plant",
    payApp: "Valuation",
    payApps: "Valuations",
    markupPresets: [
      { name: "Main contractor's preliminaries", percent: "12", basis: "direct_cost", include_in_budget: true },
      { name: "Risk allowance", percent: "5", basis: "cumulative", include_in_budget: true },
      { name: "Overheads and profit", percent: "6", basis: "cumulative", include_in_budget: false },
    ],
  },
};

let current: CountryCode = "US";

export function setRegion(country: string | null | undefined): void {
  current = country === "GB" ? "GB" : "US";
}

export function region(): CountryCode {
  return current;
}

export function terms(country: string | null | undefined = current): RegionTerms {
  return TERMS[country === "GB" ? "GB" : "US"];
}
