/** Client-side validation for decimal inputs. Values stay strings end to end; the server re-validates. */

export function decimalError(value: string, places: number, opts: { required?: boolean; max?: string; label?: string } = {}): string | undefined {
  const v = value.trim().replace(/,/g, "");
  if (v === "") return opts.required ? `${opts.label ?? "Value"} is required` : undefined;
  const re = places > 0 ? new RegExp(`^\\d+(\\.\\d{1,${places}})?$`) : /^\d+$/;
  if (!re.test(v)) return places > 0 ? `Enter a number with up to ${places} decimal places` : "Enter a whole number";
  if (opts.max !== undefined && compareDecimal(v, opts.max) > 0) return `Must be at most ${opts.max}`;
  return undefined;
}

/** Compare two non-negative decimal strings without floating point. */
export function compareDecimal(a: string, b: string): number {
  const [ai = "0", af = ""] = a.split(".");
  const [bi = "0", bf = ""] = b.split(".");
  const width = Math.max(af.length, bf.length);
  const x = BigInt(ai + af.padEnd(width, "0"));
  const y = BigInt(bi + bf.padEnd(width, "0"));
  return x === y ? 0 : x > y ? 1 : -1;
}

export function clean(value: string): string {
  const v = value.trim().replace(/,/g, "");
  return v === "" ? "0" : v;
}
