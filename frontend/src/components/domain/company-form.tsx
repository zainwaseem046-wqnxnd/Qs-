"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useVocabulary } from "@/lib/hooks";
import type { Company } from "@/lib/types";

interface Values {
  name: string;
  legal_name: string;
  company_type: string;
  trades: string;
  website: string;
  phone: string;
  email: string;
  line1: string;
  city: string;
  state_code: string;
  postal_code: string;
  notes: string;
}

function initial(c?: Company): Values {
  return {
    name: c?.name ?? "",
    legal_name: c?.legal_name ?? "",
    company_type: c?.company_type ?? "subcontractor",
    trades: c?.trades.join(", ") ?? "",
    website: c?.website ?? "",
    phone: c?.phone ?? "",
    email: c?.email ?? "",
    line1: c?.address?.line1 ?? "",
    city: c?.address?.city ?? "",
    state_code: c?.address?.state_code ?? "",
    postal_code: c?.address?.postal_code ?? "",
    notes: c?.notes ?? "",
  };
}

export function CompanyForm({ company, onSaved, onCancel }: { company?: Company; onSaved: (c: Company) => void; onCancel: () => void }) {
  const vocab = useVocabulary().data;
  const [v, setV] = useState<Values>(initial(company));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!v.name.trim()) errs.name = "Enter the company name";
    if (v.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email)) errs.email = "Enter a valid email";
    if (v.postal_code && !/^\d{5}(-\d{4})?$/.test(v.postal_code)) errs.postal_code = "Use a 5-digit or ZIP+4 code";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const hasAddress = [v.line1, v.city, v.state_code, v.postal_code].some((x) => x.trim());
    const body: Record<string, unknown> = {
      name: v.name.trim(),
      legal_name: v.legal_name,
      company_type: v.company_type,
      trades: v.trades.split(",").map((t) => t.trim()).filter(Boolean),
      website: v.website,
      phone: v.phone,
      email: v.email,
      notes: v.notes,
      address: hasAddress ? { line1: v.line1, city: v.city, state_code: v.state_code, postal_code: v.postal_code } : null,
    };
    setBusy(true);
    setError(null);
    try {
      const saved = company
        ? await api<Company>(`/companies/${company.id}`, { method: "PATCH", body: { ...body, version: company.version } })
        : await api<Company>("/companies", { method: "POST", body });
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(Object.fromEntries(Object.entries(err.fieldErrors).map(([k, m]) => [k.replace("address.", ""), m])));
        setError(err.code === "version_conflict" ? "This company was changed by someone else. Close and reopen to see the latest version." : err.message);
      } else setError("Unable to save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4" id="company-form">
      {error && <Alert tone="danger">{error}</Alert>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Company name" error={errors.name} required>{(p) => <Input {...p} value={v.name} onChange={set("name")} maxLength={200} />}</Field>
        <Field label="Type" required>{(p) => <Select {...p} value={v.company_type} onChange={set("company_type")}><Options map={vocab?.company_types} /></Select>}</Field>
        <Field label="Legal name" error={errors.legal_name}>{(p) => <Input {...p} value={v.legal_name} onChange={set("legal_name")} maxLength={200} />}</Field>
        <Field label="Trades" hint="Comma separated, e.g. Electrical, Fire Alarm">{(p) => <Input {...p} value={v.trades} onChange={set("trades")} />}</Field>
        <Field label="Email" error={errors.email}>{(p) => <Input {...p} type="email" value={v.email} onChange={set("email")} />}</Field>
        <Field label="Phone" error={errors.phone}>{(p) => <Input {...p} type="tel" value={v.phone} onChange={set("phone")} maxLength={40} />}</Field>
        <Field label="Website" error={errors.website} className="sm:col-span-2">{(p) => <Input {...p} value={v.website} onChange={set("website")} maxLength={300} />}</Field>
        <Field label="Street address" className="sm:col-span-2">{(p) => <Input {...p} value={v.line1} onChange={set("line1")} />}</Field>
        <Field label="City">{(p) => <Input {...p} value={v.city} onChange={set("city")} />}</Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="State" error={errors.state_code}>{(p) => <Select {...p} value={v.state_code} onChange={set("state_code")}><Options map={vocab?.us_states} placeholder="—" /></Select>}</Field>
          <Field label="ZIP" error={errors.postal_code}>{(p) => <Input {...p} value={v.postal_code} onChange={set("postal_code")} inputMode="numeric" />}</Field>
        </div>
        <Field label="Notes" className="sm:col-span-2">{(p) => <Textarea {...p} value={v.notes} onChange={set("notes")} rows={3} />}</Field>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={busy}>{company ? "Save changes" : "Add company"}</Button>
      </div>
    </form>
  );
}
