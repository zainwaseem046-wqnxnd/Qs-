"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Checkbox, Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { P, useVocabulary } from "@/lib/hooks";
import { parseMoneyInput } from "@/lib/money";
import { terms } from "@/lib/region";
import type { Company, Page, Project } from "@/lib/types";

const optionalDate = z.string().regex(/^(\d{4}-\d{2}-\d{2})?$/, "Use a valid date");
const schema = z
  .object({
    number: z.string().trim().min(1, "Required").max(40).regex(/^[A-Za-z0-9][A-Za-z0-9._/-]*$/, "Letters, numbers, . _ / - only"),
    name: z.string().trim().min(2, "Enter a project name").max(200),
    status: z.string().min(1),
    sector: z.string().min(1, "Select a sector"),
    project_type: z.string().max(80).optional(),
    delivery_method: z.string().min(1, "Select a delivery method"),
    contract_type: z.string().min(1, "Select a contract type"),
    our_role: z.string().min(1),
    client_company_id: z.string().optional(),
    line1: z.string().max(200).optional(),
    city: z.string().max(120).optional(),
    state_code: z.string().optional(),
    postal_code: z.string().optional(),
    county: z.string().max(120).optional(),
    start_date: optionalDate,
    planned_completion_date: optionalDate,
    actual_completion_date: optionalDate,
    original_contract_value: z
      .string()
      .refine((v) => v.trim() === "" || parseMoneyInput(v) !== null, "Enter an amount like 1,250,000.00 (max 2 decimals)"),
    currency: z.string().length(3),
    retainage_percent: z.string().regex(/^(100(\.0{1,2})?|\d{1,2}(\.\d{1,2})?)?$/, "Enter 0–100 with up to 2 decimals"),
    is_public_works: z.boolean(),
    prevailing_wage: z.boolean(),
    reporting_period_end_day: z.string().regex(/^([1-9]|[12]\d|3[01])$/, "Day 1–31"),
    description: z.string().max(10000).optional(),
  })
  .refine((v) => !v.start_date || !v.planned_completion_date || v.planned_completion_date >= v.start_date, {
    path: ["planned_completion_date"],
    message: "Must be on or after the start date",
  })
  .superRefine((v, ctx) => {
    const t = terms();
    if (v.postal_code && !t.postalPattern.test(v.postal_code.trim())) {
      ctx.addIssue({ code: "custom", path: ["postal_code"], message: t.postalError });
    }
  });

export type ProjectFormValues = z.infer<typeof schema>;

function toValues(p?: Project, homeState?: string | null, currency?: string, country?: string): ProjectFormValues {
  return {
    number: p?.number ?? "",
    name: p?.name ?? "",
    status: p?.status ?? "preconstruction",
    sector: p?.sector ?? "",
    project_type: p?.project_type ?? "",
    delivery_method: p?.delivery_method ?? "",
    contract_type: p?.contract_type ?? "",
    our_role: p?.our_role ?? (country === "GB" ? "main_contractor" : "general_contractor"),
    client_company_id: p?.client_company?.id ?? "",
    line1: p?.site_address?.line1 ?? "",
    city: p?.site_address?.city ?? "",
    state_code: p?.site_address?.state_code ?? (p ? "" : homeState ?? ""),
    postal_code: p?.site_address?.postal_code ?? "",
    county: p?.site_address?.county ?? "",
    start_date: p?.start_date ?? "",
    planned_completion_date: p?.planned_completion_date ?? "",
    actual_completion_date: p?.actual_completion_date ?? "",
    original_contract_value: p?.original_contract_value ?? "",
    currency: p?.currency ?? currency ?? "USD",
    retainage_percent: p?.retainage_percent ?? "",
    is_public_works: p?.is_public_works ?? false,
    prevailing_wage: p?.prevailing_wage ?? false,
    reporting_period_end_day: String(p?.reporting_period_end_day ?? 31),
    description: p?.description ?? "",
  };
}

function toPayload(v: ProjectFormValues, opts: { financials: boolean; edit: boolean }) {
  const n = (s?: string) => (s && s.trim() !== "" ? s.trim() : null);
  const hasAddress = [v.line1, v.city, v.state_code, v.postal_code, v.county].some((x) => n(x));
  const body: Record<string, unknown> = {
    number: v.number.trim(),
    name: v.name.trim(),
    status: v.status,
    sector: v.sector,
    project_type: n(v.project_type),
    delivery_method: v.delivery_method,
    contract_type: v.contract_type,
    our_role: v.our_role,
    client_company_id: n(v.client_company_id),
    site_address: hasAddress
      ? { line1: n(v.line1), city: n(v.city), state_code: terms().usesStates ? n(v.state_code) : null, postal_code: n(v.postal_code), county: n(v.county) }
      : null,
    start_date: n(v.start_date),
    planned_completion_date: n(v.planned_completion_date),
    currency: v.currency,
    is_public_works: v.is_public_works,
    prevailing_wage: v.prevailing_wage,
    reporting_period_end_day: Number.parseInt(v.reporting_period_end_day, 10),
    description: n(v.description),
  };
  if (opts.edit) body.actual_completion_date = n(v.actual_completion_date);
  if (opts.financials) {
    body.original_contract_value = v.original_contract_value.trim() ? parseMoneyInput(v.original_contract_value) : null;
    body.retainage_percent = n(v.retainage_percent);
  }
  return body;
}

const FIELD_MAP: Record<string, keyof ProjectFormValues> = {
  "site_address.state_code": "state_code",
  "site_address.postal_code": "postal_code",
  "site_address.city": "city",
};

export function ProjectForm({
  project,
  onSaved,
  onCancel,
}: {
  project?: Project;
  onSaved: (p: Project) => void;
  onCancel?: () => void;
}) {
  const { can, tenant } = useAuth();
  const vocab = useVocabulary().data;
  const financials = can(P.PROJECTS_FINANCIALS_VIEW);
  const companies = useQuery({
    queryKey: ["companies", "all-active"],
    queryFn: () => api<Page<Company>>("/companies", { query: { limit: 200 } }),
    enabled: can(P.COMPANIES_VIEW),
  });
  const [error, setError] = useState<string | null>(null);
  const form = useForm<ProjectFormValues>({ resolver: zodResolver(schema), defaultValues: toValues(project, tenant?.tenant.home_state, tenant?.tenant.default_currency, tenant?.tenant.country_code) });
  const t = terms(tenant?.tenant.country_code);
  const e = form.formState.errors;
  const reg = form.register;

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    const body = toPayload(values, { financials, edit: !!project });
    try {
      const saved = project
        ? await api<Project>(`/projects/${project.id}`, { method: "PATCH", body: { ...body, version: project.version } })
        : await api<Project>("/projects", { method: "POST", body });
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          const key = (FIELD_MAP[field] ?? field) as keyof ProjectFormValues;
          if (key in values) form.setError(key, { message });
        }
        setError(err.code === "version_conflict" ? "Someone else changed this project. Reload the page to see their changes before editing." : err.message);
      } else setError("Unable to save the project");
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-8">
      {error && <Alert tone="danger">{error}</Alert>}

      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-subtle">Project</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-6">
          <Field label="Project number" error={e.number?.message} required className="sm:col-span-2">
            {(p) => <Input {...p} {...reg("number")} placeholder="24-017" />}
          </Field>
          <Field label="Project name" error={e.name?.message} required className="sm:col-span-4">
            {(p) => <Input {...p} {...reg("name")} placeholder="Riverside Medical Office Building" />}
          </Field>
          <Field label="Status" error={e.status?.message} required className="sm:col-span-2">
            {(p) => <Select {...p} {...reg("status")}><Options map={vocab?.project_statuses} /></Select>}
          </Field>
          <Field label="Sector" error={e.sector?.message} required className="sm:col-span-2">
            {(p) => <Select {...p} {...reg("sector")}><Options map={vocab?.sectors} placeholder="Select…" /></Select>}
          </Field>
          <Field label="Project type" hint="e.g. Medical office, K-12, Warehouse" error={e.project_type?.message} className="sm:col-span-2">
            {(p) => <Input {...p} {...reg("project_type")} />}
          </Field>
          <Field label="Delivery method" error={e.delivery_method?.message} required className="sm:col-span-2">
            {(p) => <Select {...p} {...reg("delivery_method")}><Options map={vocab?.delivery_methods} placeholder="Select…" /></Select>}
          </Field>
          <Field label="Contract type" error={e.contract_type?.message} required className="sm:col-span-2">
            {(p) => <Select {...p} {...reg("contract_type")}><Options map={vocab?.contract_types} placeholder="Select…" /></Select>}
          </Field>
          <Field label="Our role" error={e.our_role?.message} required className="sm:col-span-2">
            {(p) => <Select {...p} {...reg("our_role")}><Options map={vocab?.our_roles} /></Select>}
          </Field>
          <Field
            label="Client / owner"
            hint={can(P.COMPANIES_VIEW) ? "Add companies in the Directory" : undefined}
            error={e.client_company_id?.message}
            className="sm:col-span-3"
          >
            {(p) => (
              <Select {...p} {...reg("client_company_id")} disabled={!can(P.COMPANIES_VIEW)}>
                <option value="">Not set</option>
                {companies.data?.items.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
                {project?.client_company && !companies.data?.items.some((c) => c.id === project.client_company?.id) && (
                  <option value={project.client_company.id}>{project.client_company.name}</option>
                )}
              </Select>
            )}
          </Field>
          <Field label="Description" error={e.description?.message} className="sm:col-span-6">
            {(p) => <Textarea {...p} {...reg("description")} rows={3} />}
          </Field>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-subtle">Site location</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-6">
          <Field label="Street address" error={e.line1?.message} className="sm:col-span-6">
            {(p) => <Input {...p} {...reg("line1")} autoComplete="off" />}
          </Field>
          <Field label="City" error={e.city?.message} className="sm:col-span-2">
            {(p) => <Input {...p} {...reg("city")} />}
          </Field>
          {t.usesStates && (
            <Field label="State" error={e.state_code?.message} className="sm:col-span-2">
              {(p) => <Select {...p} {...reg("state_code")}><Options map={vocab?.us_states} placeholder="Select…" /></Select>}
            </Field>
          )}
          <Field label="County" error={e.county?.message} className={t.usesStates ? "sm:col-span-1" : "sm:col-span-2"}>
            {(p) => <Input {...p} {...reg("county")} />}
          </Field>
          <Field label={t.postalLabel} error={e.postal_code?.message} className={t.usesStates ? "sm:col-span-1" : "sm:col-span-2"}>
            {(p) => <Input {...p} {...reg("postal_code")} placeholder={t.postalPlaceholder} autoCapitalize="characters" />}
          </Field>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-subtle">Schedule</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Start date" error={e.start_date?.message}>{(p) => <Input {...p} {...reg("start_date")} type="date" />}</Field>
          <Field label="Planned completion" error={e.planned_completion_date?.message}>
            {(p) => <Input {...p} {...reg("planned_completion_date")} type="date" />}
          </Field>
          {project && (
            <Field label="Actual completion" error={e.actual_completion_date?.message}>
              {(p) => <Input {...p} {...reg("actual_completion_date")} type="date" />}
            </Field>
          )}
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-subtle">Contract & reporting</h3>
        {!financials && <Alert tone="info">Commercial values are hidden for your role.</Alert>}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          {financials && (
            <>
              <Field label="Original contract value" hint="As awarded. Revisions come from approved change orders." error={e.original_contract_value?.message} className="sm:col-span-2">
                {(p) => <Input {...p} {...reg("original_contract_value")} inputMode="decimal" placeholder="12,500,000.00" className="num" />}
              </Field>
              <Field label={`${t.retainage} %`} error={e.retainage_percent?.message}>
                {(p) => <Input {...p} {...reg("retainage_percent")} inputMode="decimal" placeholder="10.00" className="num" />}
              </Field>
            </>
          )}
          <Field label="Currency" error={e.currency?.message}>
            {(p) => (
              <Select {...p} {...reg("currency")}>
                {(vocab?.currencies ?? ["USD"]).map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Reporting period ends on day" hint="31 = month end" error={e.reporting_period_end_day?.message}>
            {(p) => <Input {...p} {...reg("reporting_period_end_day")} inputMode="numeric" />}
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Checkbox label="Public works project" hint="Enables public-works compliance workflows (Phase 5)" {...reg("is_public_works")} />
          {t.usesStates && <Checkbox label="Prevailing wage applies" hint="Davis-Bacon or state prevailing wage" {...reg("prevailing_wage")} />}
        </div>
      </section>

      <div className="flex justify-end gap-2 border-t border-border pt-4">
        {onCancel && <Button variant="secondary" onClick={onCancel}>Cancel</Button>}
        <Button type="submit" loading={form.formState.isSubmitting}>{project ? "Save changes" : "Create project"}</Button>
      </div>
    </form>
  );
}
