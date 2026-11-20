"use client";

import { useQuery } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { clean, decimalError } from "@/lib/decimal";
import { formatDecimal } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { terms } from "@/lib/region";
import type { CostCode, EstimateLine, LineCalc } from "@/lib/types";

const LINE_TYPES: Record<string, string> = {
  item: "Measured item",
  allowance: "Allowance",
  provisional_sum: "Provisional sum",
  prime_cost_sum: "Prime cost sum",
  daywork: "Daywork",
};

type NumField = "quantity" | "labour_hours_per_unit" | "labour_rate" | "material_rate" | "material_waste_percent" | "equipment_rate" | "subcontract_rate" | "other_rate";
const PLACES: Record<NumField, number> = {
  quantity: 4, labour_hours_per_unit: 4, labour_rate: 6, material_rate: 6, material_waste_percent: 2,
  equipment_rate: 6, subcontract_rate: 6, other_rate: 6,
};

interface Values extends Record<NumField, string> {
  cost_code_id: string;
  line_type: string;
  inclusion: string;
  alternate_label: string;
  description: string;
  unit: string;
  notes: string;
}

function initial(line: EstimateLine | null): Values {
  const z = (v: string | undefined) => (v && !/^0(\.0*)?$/.test(v) ? formatDecimal(v).replace(/,/g, "") : "");
  return {
    cost_code_id: line?.cost_code?.id ?? "",
    line_type: line?.line_type ?? "item",
    inclusion: line?.inclusion ?? "base",
    alternate_label: line?.alternate_label ?? "",
    description: line?.description ?? "",
    unit: line?.unit ?? "",
    notes: line?.notes ?? "",
    quantity: line ? formatDecimal(line.quantity).replace(/,/g, "") : "",
    labour_hours_per_unit: z(line?.labour_hours_per_unit),
    labour_rate: z(line?.labour_rate),
    material_rate: z(line?.material_rate),
    material_waste_percent: z(line?.material_waste_percent),
    equipment_rate: z(line?.equipment_rate),
    subcontract_rate: z(line?.subcontract_rate),
    other_rate: z(line?.other_rate),
  };
}

function numericErrors(v: Values): Partial<Record<NumField, string>> {
  const errs: Partial<Record<NumField, string>> = {};
  for (const f of Object.keys(PLACES) as NumField[]) {
    const e = decimalError(v[f], PLACES[f], { required: f === "quantity", label: "Quantity", max: f === "material_waste_percent" ? "100" : undefined });
    if (e) errs[f] = e;
  }
  return errs;
}

export function EstimateLineDialog({
  open,
  onOpenChange,
  line,
  editable,
  currency,
  codes,
  onSave,
  onDelete,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  line: EstimateLine | null;
  editable: boolean;
  currency: string;
  codes: CostCode[];
  onSave: (body: Record<string, unknown>) => Promise<void>;
  onDelete?: () => Promise<void>;
}) {
  const t = terms();
  const [v, setV] = useState<Values>(initial(line));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [debounced, setDebounced] = useState<Values>(v);

  useEffect(() => {
    if (open) {
      const init = initial(line);
      setV(init);
      setDebounced(init);
      setErrors({});
      setError(null);
    }
  }, [open, line]);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(v), 300);
    return () => clearTimeout(id);
  }, [v]);

  const numErrs = numericErrors(debounced);
  const previewBody = Object.fromEntries((Object.keys(PLACES) as NumField[]).map((f) => [f, clean(debounced[f])]));
  const preview = useQuery({
    queryKey: ["calc-line", previewBody],
    queryFn: () => api<LineCalc>("/estimating/calculate-line", { method: "POST", body: previewBody }),
    enabled: open && Object.keys(numErrs).length === 0 && debounced.quantity.trim() !== "",
    staleTime: Infinity,
  });
  const calc = preview.data ?? line?.calc;

  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });

  const submit = async () => {
    const errs: Record<string, string> = { ...numericErrors(v) };
    if (!v.description.trim()) errs.description = "Enter a description";
    if (!v.unit.trim()) errs.unit = "Enter a unit, e.g. m², SF, nr, item";
    if (v.inclusion === "alternate" && !v.alternate_label.trim()) errs.alternate_label = "Name the alternate";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      await onSave({
        cost_code_id: v.cost_code_id || null,
        line_type: v.line_type,
        inclusion: v.inclusion,
        alternate_label: v.inclusion === "alternate" ? v.alternate_label.trim() : null,
        description: v.description.trim(),
        unit: v.unit.trim(),
        notes: v.notes.trim() || null,
        ...Object.fromEntries((Object.keys(PLACES) as NumField[]).map((f) => [f, clean(v[f])])),
      });
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setError(err.message);
      } else setError("Unable to save the line");
    } finally {
      setBusy(false);
    }
  };

  const num = (f: NumField, label: string, hint?: string) => (
    <Field label={label} hint={hint} error={errors[f] ?? numErrs[f]} required={f === "quantity"}>
      {(p) => <Input {...p} value={v[f]} onChange={set(f)} inputMode="decimal" className="num" disabled={!editable} placeholder={f === "quantity" ? "" : "0"} />}
    </Field>
  );

  const rows: [string, string | undefined, string | undefined][] = calc
    ? [
        [`${t.labour}`, calc.labour_unit, calc.labour_total],
        ["Material (incl. waste)", calc.material_unit, calc.material_total],
        [t.equipment, calc.equipment_unit, calc.equipment_total],
        ["Subcontract", calc.subcontract_unit, calc.subcontract_total],
        ["Other", calc.other_unit, calc.other_total],
      ]
    : [];

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      wide
      title={line ? (editable ? "Edit line" : "Line build-up") : "Add line"}
      footer={
        editable ? (
          <>
            {line && onDelete && <ConfirmButton label={<><Trash2 className="size-4" />Delete</>} title="Delete this line?" description="The line is removed from this draft version." confirmLabel="Delete line" onConfirm={async () => { await onDelete(); onOpenChange(false); }} />}
            <div className="flex-1" />
            <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button loading={busy} onClick={submit}>{line ? "Save line" : "Add line"}</Button>
          </>
        ) : (
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Close</Button>
        )
      }
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          {!editable && <Alert tone="info">This version is locked. Create a new version to change it.</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Description" error={errors.description} required className="sm:col-span-2">
              {(p) => <Input {...p} value={v.description} onChange={set("description")} maxLength={500} disabled={!editable} />}
            </Field>
            <Field label="Cost code" error={errors.cost_code_id}>
              {(p) => (
                <Select {...p} value={v.cost_code_id} onChange={set("cost_code_id")} disabled={!editable}>
                  <option value="">Unassigned</option>
                  {codes.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}
                </Select>
              )}
            </Field>
            <Field label="Line type">
              {(p) => <Select {...p} value={v.line_type} onChange={set("line_type")} disabled={!editable}>{Object.entries(LINE_TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select>}
            </Field>
            <Field label="Scope">
              {(p) => (
                <Select {...p} value={v.inclusion} onChange={set("inclusion")} disabled={!editable}>
                  <option value="base">Base scope</option>
                  <option value="alternate">Alternate / option (priced separately)</option>
                  <option value="excluded">Excluded (for information)</option>
                </Select>
              )}
            </Field>
            {v.inclusion === "alternate" && (
              <Field label="Alternate name" error={errors.alternate_label} required>
                {(p) => <Input {...p} value={v.alternate_label} onChange={set("alternate_label")} maxLength={80} disabled={!editable} placeholder="Alt 1 — upgraded facade" />}
              </Field>
            )}
            {num("quantity", "Quantity")}
            <Field label="Unit" error={errors.unit} required>
              {(p) => <Input {...p} value={v.unit} onChange={set("unit")} maxLength={20} disabled={!editable} placeholder="m², SF, nr, item" />}
            </Field>
          </div>
          <fieldset className="grid gap-4 rounded-md border border-border p-4 sm:grid-cols-2">
            <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-subtle">Rates per unit ({currency})</legend>
            {num("labour_hours_per_unit", `${t.labour} hours per unit`)}
            {num("labour_rate", `${t.labour} rate per hour`)}
            {num("material_rate", "Material rate")}
            {num("material_waste_percent", "Material waste %")}
            {num("equipment_rate", `${t.equipment} rate`)}
            {num("subcontract_rate", "Subcontract rate")}
            {num("other_rate", "Other rate", "Allowances and lump sums: quantity 1 with the sum here")}
          </fieldset>
          <Field label="Notes">{(p) => <Textarea {...p} value={v.notes} onChange={set("notes")} rows={2} disabled={!editable} />}</Field>
        </div>
        <aside className="h-fit rounded-md border border-border bg-surface-2 p-4" aria-live="polite">
          <h3 className="text-sm font-semibold">Calculation build-up</h3>
          <p className="mt-0.5 text-xs text-subtle">Calculated by the server engine. Totals are quantity × unit rate, rounded once per component.</p>
          {calc ? (
            <table className="mt-3 w-full text-xs">
              <thead><tr className="text-left text-subtle"><th className="pb-1 font-medium">Component</th><th className="pb-1 text-right font-medium">Per unit</th><th className="pb-1 text-right font-medium">Total</th></tr></thead>
              <tbody className="num">
                {rows.map(([name, unit, total]) => (
                  <tr key={name} className="border-t border-border">
                    <td className="py-1.5">{name}</td>
                    <td className="py-1.5 text-right">{formatDecimal(unit, 2)}</td>
                    <td className="py-1.5 text-right">{formatMoney(total, currency)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border-strong font-semibold">
                  <td className="py-2">Line total</td>
                  <td className="py-2 text-right">{formatDecimal(calc.unit_cost, 2)}</td>
                  <td className="py-2 text-right">{formatMoney(calc.total, currency)}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="mt-3 text-xs text-muted">Enter a quantity to see the build-up.</p>
          )}
          {calc && calc.labour_hours !== "0.0000" && <p className="num mt-2 text-xs text-muted">{t.labour} hours: {formatDecimal(calc.labour_hours)}</p>}
          {preview.isFetching && <p className="mt-2 text-xs text-subtle">Recalculating…</p>}
        </aside>
      </div>
    </Dialog>
  );
}
