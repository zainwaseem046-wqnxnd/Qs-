"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Alert } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import { ApiError } from "@/lib/api";
import { clean, decimalError } from "@/lib/decimal";
import { terms } from "@/lib/region";
import type { Markup } from "@/lib/types";

interface Row {
  name: string;
  percent: string;
  basis: "direct_cost" | "cumulative";
  include_in_budget: boolean;
}

export function MarkupsDialog({ open, onOpenChange, markups, onSave }: { open: boolean; onOpenChange: (o: boolean) => void; markups: Markup[]; onSave: (rows: Row[]) => Promise<void> }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setRows(markups.map((m) => ({ name: m.name, percent: m.percent.replace(/\.?0+$/, ""), basis: m.basis, include_in_budget: m.include_in_budget })));
      setError(null);
    }
  }, [open, markups]);
  const update = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const move = (i: number, d: number) => {
    const next = [...rows];
    const [r] = next.splice(i, 1);
    next.splice(i + d, 0, r!);
    setRows(next);
  };
  const save = async () => {
    for (const [i, r] of rows.entries()) {
      if (!r.name.trim()) return setError(`Row ${i + 1}: enter a name`);
      const e = decimalError(r.percent, 4, { required: true, label: "Percentage", max: "1000" });
      if (e) return setError(`Row ${i + 1}: ${e}`);
    }
    setBusy(true);
    setError(null);
    try {
      await onSave(rows.map((r) => ({ ...r, name: r.name.trim(), percent: clean(r.percent) })));
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save markups");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Markups" description="Applied in order. 'Direct cost' uses the direct cost; 'Running total' compounds on the direct cost plus earlier markups."
      footer={<><Button variant="secondary" onClick={() => setRows([...rows, ...terms().markupPresets.filter((p) => !rows.some((r) => r.name === p.name))])}>Add typical markups</Button><div className="flex-1" /><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Save markups</Button></>}>
      <div className="space-y-3">
        {error && <Alert tone="danger">{error}</Alert>}
        {rows.length === 0 && <p className="text-sm text-muted">No markups. Add rows below or use typical markups.</p>}
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-1 items-center gap-2 rounded-md border border-border p-3 sm:grid-cols-[1fr_6rem_10rem_auto_auto]">
            <Input aria-label={`Markup ${i + 1} name`} value={r.name} onChange={(e) => update(i, { name: e.target.value })} maxLength={120} placeholder="Name" />
            <div className="flex items-center gap-1">
              <Input aria-label={`Markup ${i + 1} percent`} value={r.percent} onChange={(e) => update(i, { percent: e.target.value })} inputMode="decimal" className="num" />
              <span className="text-sm text-muted">%</span>
            </div>
            <Select aria-label={`Markup ${i + 1} basis`} value={r.basis} onChange={(e) => update(i, { basis: e.target.value as Row["basis"] })}>
              <option value="direct_cost">Direct cost</option>
              <option value="cumulative">Running total</option>
            </Select>
            <label className="flex items-center gap-2 text-xs" title="Profit and fee are usually not part of the cost budget">
              <input type="checkbox" className="size-4 accent-[var(--accent)]" checked={r.include_in_budget} onChange={(e) => update(i, { include_in_budget: e.target.checked })} />
              In budget
            </label>
            <div className="flex">
              <Button size="sm" variant="ghost" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp className="size-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Move down" disabled={i === rows.length - 1} onClick={() => move(i, 1)}><ArrowDown className="size-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Remove markup" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 className="size-4" /></Button>
            </div>
          </div>
        ))}
        <Button size="sm" variant="secondary" onClick={() => setRows([...rows, { name: "", percent: "", basis: "cumulative", include_in_budget: true }])}><Plus className="size-4" />Add markup</Button>
      </div>
    </Dialog>
  );
}
