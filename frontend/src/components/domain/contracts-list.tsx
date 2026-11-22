"use client";

import { useQuery } from "@tanstack/react-query";
import { FileSignature, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Options, Select } from "@/components/ui/form";
import { DataTable, type Column } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { clean, decimalError } from "@/lib/decimal";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { terms } from "@/lib/region";
import type { Company, ContractKind, ContractListItem, ContractRecord, ContractVocab, Page, ProjectListItem } from "@/lib/types";

export const STATUS_TONES = { draft: "neutral", executed: "success", closed: "accent", void: "danger" } as const;

export function useContractVocab() {
  return useQuery({ queryKey: ["contract-vocab"], queryFn: () => api<ContractVocab>("/contracts/vocabulary"), staleTime: Infinity });
}

export function detailPath(kind: ContractKind, id: string) {
  return kind === "contracts" ? `/contracts/${id}` : `/commitments/${id}`;
}

function NewDialog({ kind, open, onOpenChange, projectId }: { kind: ContractKind; open: boolean; onOpenChange: (o: boolean) => void; projectId?: string }) {
  const router = useRouter();
  const vocab = useContractVocab().data;
  const t = terms();
  const isPrime = kind === "contracts";
  const [project, setProject] = useState(projectId ?? "");
  const [type, setType] = useState<"subcontract" | "purchase_order">("subcontract");
  const [title, setTitle] = useState("");
  const [form, setForm] = useState("");
  const [party, setParty] = useState("");
  const [retention, setRetention] = useState("");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const projects = useQuery({ queryKey: ["projects", "picker"], queryFn: () => api<Page<ProjectListItem>>("/projects", { query: { limit: 200, sort: "name", order: "asc" } }), enabled: open && !projectId });
  const companies = useQuery({ queryKey: ["companies", "all-active"], queryFn: () => api<Page<Company>>("/companies", { query: { limit: 200 } }), enabled: open });
  useEffect(() => {
    if (open) {
      setProject(projectId ?? ""); setTitle(""); setForm(""); setParty(""); setRetention(""); setDays(""); setError(null); setType("subcontract");
    }
  }, [open, projectId]);
  const forms = isPrime ? vocab?.prime_forms : vocab?.subcontract_forms;
  const submit = async () => {
    setError(null);
    if (!project) return setError("Choose a project");
    if (title.trim().length < 2) return setError("Enter a title");
    if (!form) return setError("Choose a contract form");
    if (!isPrime && !party) return setError("Choose the subcontractor or supplier");
    const re = decimalError(retention, 2, { max: "100", label: t.retainage });
    if (re) return setError(`${t.retainage}: ${re}`);
    if (days && !/^\d{1,3}$/.test(days)) return setError("Payment terms must be a number of days");
    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        title: title.trim(), contract_form: form,
        retention_percent: retention.trim() ? clean(retention) : null,
        payment_terms_days: days ? Number.parseInt(days, 10) : null,
      };
      if (isPrime) body.client_company_id = party || null;
      else Object.assign(body, { commitment_type: type, vendor_company_id: party });
      const rec = await api<ContractRecord>(`/projects/${project}/${kind}`, { method: "POST", body });
      router.push(detailPath(kind, rec.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={isPrime ? "New prime contract" : "New subcontract or purchase order"} description="Created as a draft. Add lines, then execute it once signed."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={submit}>Create draft</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        {!projectId && (
          <Field label="Project" required className="sm:col-span-2">
            {(p) => <Select {...p} value={project} onChange={(e) => setProject(e.target.value)}><option value="">Select a project…</option>{projects.data?.items.map((pr) => <option key={pr.id} value={pr.id}>{pr.number} — {pr.name}</option>)}</Select>}
          </Field>
        )}
        {!isPrime && (
          <Field label="Type" required>
            {(p) => <Select {...p} value={type} onChange={(e) => { const v = e.target.value as typeof type; setType(v); if (v === "purchase_order") setForm("purchase_order"); }}><Options map={vocab?.commitment_types} /></Select>}
          </Field>
        )}
        <Field label={isPrime ? "Client / employer" : "Subcontractor / supplier"} required={!isPrime} className={isPrime ? "sm:col-span-2" : undefined}>
          {(p) => <Select {...p} value={party} onChange={(e) => setParty(e.target.value)}><option value="">{isPrime ? "Not set" : "Select a company…"}</option>{companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}
        </Field>
        <Field label="Title" required className="sm:col-span-2">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder={isPrime ? "Main construction contract" : "Structural steel package"} />}</Field>
        <Field label="Contract form" required className="sm:col-span-2">{(p) => <Select {...p} value={form} onChange={(e) => setForm(e.target.value)}><Options map={forms} placeholder="Select…" /></Select>}</Field>
        <Field label={`${t.retainage} %`}>{(p) => <Input {...p} value={retention} onChange={(e) => setRetention(e.target.value)} inputMode="decimal" className="num" placeholder={t.retainage === "Retention" ? "3" : "10"} />}</Field>
        <Field label="Payment terms (days)">{(p) => <Input {...p} value={days} onChange={(e) => setDays(e.target.value)} inputMode="numeric" placeholder="30" />}</Field>
      </div>
    </Dialog>
  );
}

export function ContractsList({ kind, projectId, canCreate = true }: { kind: ContractKind; projectId?: string; canCreate?: boolean }) {
  const router = useRouter();
  const { can } = useAuth();
  const vocab = useContractVocab().data;
  const [open, setOpen] = useState(false);
  const isPrime = kind === "contracts";
  const q = useQuery({ queryKey: [kind, projectId ?? "all"], queryFn: () => api<ContractListItem[]>(`/${kind}`, { query: { project_id: projectId } }) });
  const columns: Column<ContractListItem>[] = [
    { key: "number", header: "No.", cell: (r) => <span className="num font-medium">{r.number}</span> },
    { key: "title", header: "Title", cell: (r) => <div className="min-w-48"><p className="font-medium">{r.title}</p>{!isPrime && <p className="text-xs text-subtle">{vocab?.commitment_types[r.commitment_type ?? ""] ?? r.commitment_type}</p>}</div> },
    { key: "party", header: isPrime ? "Client" : "Vendor", cell: (r) => r.counterparty ?? <span className="text-subtle">—</span> },
    ...(projectId ? [] : [{ key: "project", header: "Project", cell: (r: ContractListItem) => <span className="text-muted">{r.project_number} — {r.project_name}</span> }]),
    { key: "status", header: "Status", cell: (r) => <Badge tone={STATUS_TONES[r.status as keyof typeof STATUS_TONES] ?? "neutral"}>{vocab?.statuses[r.status] ?? r.status}</Badge> },
    { key: "executed", header: "Executed", cell: (r) => <span className="num text-muted">{formatDate(r.executed_date)}</span> },
    { key: "value", header: "Value", align: "right", cell: (r) => formatMoney(r.original_sum ?? r.current_total, r.currency) },
  ];
  const edit = can(isPrime ? P.CONTRACTS_EDIT : P.COMMITMENTS_EDIT);
  return (
    <>
      {canCreate && edit && (
        <div className="flex justify-end border-b border-border p-4">
          <Button onClick={() => setOpen(true)}><Plus className="size-4" />{isPrime ? "New prime contract" : "New subcontract / PO"}</Button>
        </div>
      )}
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? (
        <EmptyState icon={<FileSignature className="size-6" />} title={isPrime ? "No prime contracts yet" : "No subcontracts or purchase orders yet"} description={isPrime ? "Record the contract with your client: form, sum analysis, retention and key dates." : "Commit cost to subcontractors and suppliers against your budget."} />
      ) : (
        <DataTable caption={isPrime ? "Prime contracts" : "Commitments"} columns={columns} rows={q.data} rowKey={(r) => r.id} onRowClick={(r) => router.push(detailPath(kind, r.id))} />
      )}
      <NewDialog kind={kind} open={open} onOpenChange={setOpen} projectId={projectId} />
    </>
  );
}
