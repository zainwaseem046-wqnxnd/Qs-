/**
 * Money display helpers.
 *
 * The API sends monetary values as decimal strings ("12500000.00"). The UI never converts them to
 * JavaScript numbers (binary floating point). Formatting is done with string and BigInt arithmetic only.
 * The UI performs no financial calculations; all calculations happen server-side.
 */

const SYMBOLS: Record<string, string> = { USD: "$", CAD: "CA$", AUD: "A$", MXN: "MX$", GBP: "£", EUR: "€" };

const DECIMAL_RE = /^-?\d+(\.\d+)?$/;

export function isDecimalString(value: unknown): value is string {
  return typeof value === "string" && DECIMAL_RE.test(value.trim());
}

function groupThousands(intPart: string): string {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** Round a decimal string half-up to `places` decimals, returning [negative, integer, fraction]. */
function roundDecimal(value: string, places: number): [boolean, string, string] {
  const negative = value.startsWith("-");
  const [intRaw = "0", fracRaw = ""] = value.replace("-", "").split(".");
  const padded = (fracRaw + "0".repeat(places + 1)).slice(0, places + 1);
  let scaled = BigInt(intRaw + padded.slice(0, places));
  if (Number(padded[places] ?? "0") >= 5) scaled += 1n;
  const s = scaled.toString().padStart(places + 1, "0");
  const integer = places === 0 ? s : s.slice(0, -places);
  const fraction = places === 0 ? "" : s.slice(-places);
  const isZero = /^0*$/.test(integer + fraction);
  return [negative && !isZero, integer.replace(/^0+(?=\d)/, ""), fraction];
}

export function formatMoney(value: string | null | undefined, currency = "USD", opts: { cents?: boolean } = {}): string {
  if (value === null || value === undefined || value === "") return "—";
  if (!isDecimalString(value)) return "—";
  const places = opts.cents === false ? 0 : 2;
  const [negative, integer, fraction] = roundDecimal(value.trim(), places);
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  const body = groupThousands(integer) + (places ? `.${fraction}` : "");
  return negative ? `(${symbol}${body})` : `${symbol}${body}`;
}

/** Compact display for dashboards: $12.5M, $940K, $1.25B (rounded half-up for display only). */
export function formatMoneyCompact(value: string | null | undefined, currency = "USD"): string {
  if (!isDecimalString(value ?? "")) return "—";
  const v = (value as string).trim();
  const [negative, integer] = roundDecimal(v, 0);
  const digits = integer.length;
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  const units: [number, string][] = [
    [12, "T"],
    [9, "B"],
    [6, "M"],
    [3, "K"],
  ];
  for (const [exp, suffix] of units) {
    if (digits > exp) {
      const whole = integer.slice(0, digits - exp);
      const rest = integer.slice(digits - exp);
      const decimals = whole.length >= 3 ? 0 : whole.length === 2 ? 1 : 2;
      const [, i, f] = roundDecimal(`${whole}.${rest}`, decimals);
      const trimmed = f.replace(/0+$/, "");
      const out = `${symbol}${groupThousands(i)}${trimmed ? `.${trimmed}` : ""}${suffix}`;
      return negative ? `(${out})` : out;
    }
  }
  return formatMoney(v, currency, { cents: false });
}

export function formatPercent(value: string | null | undefined): string {
  if (!isDecimalString(value ?? "")) return "—";
  const [negative, integer, fraction] = roundDecimal((value as string).trim(), 2);
  const trimmed = fraction.replace(/0+$/, "");
  return `${negative ? "-" : ""}${integer}${trimmed ? `.${trimmed}` : ""}%`;
}

/** Normalise user input ("$1,250,000.5") to an API decimal string, or null if invalid. Never uses floats. */
export function parseMoneyInput(input: string): string | null {
  const cleaned = input.replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) return null;
  const [i = "0", f = ""] = cleaned.split(".");
  return `${i.replace(/^0+(?=\d)/, "")}.${(f + "00").slice(0, 2)}`;
}
