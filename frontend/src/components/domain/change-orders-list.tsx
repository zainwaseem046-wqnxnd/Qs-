"use client";

import { useQuery } from "@tanstack/react-query";
import { GitPullRequestArrow, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { DataTable, type Column } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { region } from "@/lib/region";
import type { ChangeOrder, ChangeOrderListItem, ContractListItem } from "@/lib/types";

export const CO_TONES = { draft: "neutral", submitted: "accent", approved: "success", rejected: "danger", withdrawn: "neutral" } as const;

export function useChangeReference() {
  return useQuery({
    queryKey: ["change-reference"],
    queryFn: () => api<{ reasons: Record<string, string>; statuses: Record<string, string> }>("/change-orders/reference"),
    staleTime: Infinity,
  });
}

export function changesLabel(): string {
  return region() === "GB" ? "Variations" : "Change orders";
}

export function NewChangeOrderDialog({ open, onOpenChange, target, projectId }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  target?: { type: "contract" | "commitment"; id: string; label: string };
  projectId?: string;
}) {
  const router = useRouter();
  const { can } = useAuth();
  const ref = useChangeReference().data;
  const [targetKey, setTargetKey] = useState("");
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("client_instruction");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [notified, setNotified] = useState("");
  const [due, setDue] = useState("");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const contracts = useQuery({ queryKey: ["contracts", "executed", projectId ?? "all"], queryFn: () => api<ContractListItem[]>("/contracts", { query: { status: "executed", project_id: projectId } }), enabled: open && !target && can(P.CONTRACTS_VIEW) });
  const commitments = useQuery({ queryKey: ["commitments", "executed", projectId ?? "all"], queryFn: () => api<ContractListItem[]>("/commitments", { query: { status: "executed", project_id: projectId } }), enabled: open && !target && can(P.COMMITMENTS_VIEW) });
  useEffect(() => {
    if (open) {
      setTargetKey(target ? `${target.type}:${target.id}` : "");
      setTitle(""); setReason("client_instruction"); setReference(""); setDescription(""); setNotified(""); setDue(""); setDays(""); setError(null);
    }
  }, [open, target]);
  const submit = async () => {
    setError(null);
    if (!targetKey) return setError("Choose the signed contract or subcontract this change applies to");
    if (title.trim().length < 2) return setError("Enter a title");
    if (days && !/^-?\d{1,4}$/.test(days)) return setError("Schedule impact must be a whole number of days");
    if (notified && due && due < notified) return setError("Response due date must be on or after the notified date");
    const [type, id] = targetKey.split(":");
    setBusy(true);
    try {
      const co = await api<ChangeOrder>("/change-orders", {
        method: "POST",
        body: { target_type: type, target_id: id, title: title.trim(), reason, reference: reference.trim() || null, description: description.trim() || null, notified_date: notified || null, response_due_date: due || null, schedule_impact_days: days ? Number.parseInt(days, 10) : null },
      });
      router.push(`/change-orders/${co.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create");
    } finally {
      setBusy(false);
    }
  };
  const uk = region() === "GB";
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title={uk ? "New variation / compensation event" : "New change order"} description="Created as a draft. Price it, then submit it for a decision."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={submit}>Create draft</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        {target ? (
          <p className="text-sm text-muted sm:col-span-2">Against <span className="font-medium text-fg">{target.label}</span></p>
        ) : (
          <Field label="Applies to" hint="Only signed (executed) contracts and subcontracts can be changed" required className="sm:col-span-2">
            {(p) => (
              <Select {...p} value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
                <option value="">Select…</option>
                {!!contracts.data?.length && <optgroup label="Client contracts (revenue)">{contracts.data.map((c) => <option key={c.id} value={`contract:${c.id}`}>{c.project_number} · {c.number} {c.title}{c.counterparty ? ` — ${c.counterparty}` : ""}</option>)}</optgroup>}
                {!!commitments.data?.length && <optgroup label="Subcontracts & POs (cost)">{commitments.data.map((c) => <option key={c.id} value={`commitment:${c.id}`}>{c.project_number} · {c.number} {c.title}{c.counterparty ? ` — ${c.counterparty}` : ""}</option>)}</optgroup>}
              </Select>
            )}
          </Field>
        )}
        <Field label="Title" required className="sm:col-span-2">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Additional canopy at loading bay" />}</Field>
        <Field label="Reason">{(p) => <Select {...p} value={reason} onChange={(e) => setReason(e.target.value)}><Options map={ref?.reasons} /></Select>}</Field>
        <Field label="Reference" hint={uk ? "e.g. AI-014, early warning EW-07" : "e.g. CCD-3, RFI-112, ASI-07"}>{(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}</Field>
        <Field label="Notified date">{(p) => <Input {...p} type="date" value={notified} onChange={(e) => setNotified(e.target.value)} />}</Field>
        <Field label="Response due" hint={uk ? "NEC: quotation and reply periods are time-barred" : "Contractual notice / pricing deadline"}>{(p) => <Input {...p} type="date" value={due} onChange={(e) => setDue(e.target.value)} />}</Field>
        <Field label="Schedule impact (days)" hint="Negative for time saved">{(p) => <Input {...p} value={days} onChange={(e) => setDays(e.target.value)} inputMode="numeric" />}</Field>
        <Field label="Description" className="sm:col-span-2">{(p) => <Textarea {...p} value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />}</Field>
      </div>
    </Dialog>
  );
}

export function ChangeOrdersList({ projectId, contractId, commitmentId, canCreate = true, target }: {
  projectId?: string; contractId?: string; commitmentId?: string; canCreate?: boolean;
  target?: { type: "contract" | "commitment"; id: string; label: string };
}) {
  const router = useRouter();
  const { can } = useAuth();
  const ref = useChangeReference().data;
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["change-orders", { projectId, contractId, commitmentId, status }],
    queryFn: () => api<ChangeOrderListItem[]>("/change-orders", { query: { project_id: projectId, contract_id: contractId, commitment_id: commitmentId, status } }),
  });
  const columns: Column<ChangeOrderListItem>[] = [
    { key: "number", header: "No.", cell: (r) => <span className="num font-medium">{r.number}</span> },
    { key: "title", header: "Title", cell: (r) => <div className="min-w-48"><p className="font-medium">{r.title}</p><p className="text-xs text-subtle">{r.label} · {r.target.number}{r.target.counterparty ? ` — ${r.target.counterparty}` : ""}</p></div> },
    ...(projectId || contractId || commitmentId ? [] : [{ key: "project", header: "Project", cell: (r: ChangeOrderListItem) => <span className="text-muted">{r.project_number}</span> }]),
    { key: "status", header: "Status", cell: (r) => <span className="flex gap-1"><Badge tone={CO_TONES[r.status as keyof typeof CO_TONES]}>{ref?.statuses[r.status] ?? r.status}</Badge>{r.overdue && <Badge tone="warning">Overdue</Badge>}</span> },
    { key: "due", header: "Response due", cell: (r) => <span className="num text-muted">{formatDate(r.response_due_date)}</span> },
    { key: "total", header: "Amount", align: "right", cell: (r) => formatMoney(r.total, r.currency) },
  ];
  return (
    <>
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <Select className="w-48" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}><Options map={ref?.statuses} placeholder="All statuses" /></Select>
        <div className="flex-1" />
        {canCreate && can(P.CHANGES_EDIT) && <Button onClick={() => setOpen(true)}><Plus className="size-4" />{region() === "GB" ? "New variation" : "New change order"}</Button>}
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? (
        <EmptyState icon={<GitPullRequestArrow className="size-6" />} title={status ? "Nothing with this status" : `No ${changesLabel().toLowerCase()} yet`} description="Raise changes against signed contracts and subcontracts; approved changes revise the contract sum, budget and committed cost." />
      ) : (
        <DataTable caption={changesLabel()} columns={columns} rows={q.data} rowKey={(r) => r.id} onRowClick={(r) => router.push(`/change-orders/${r.id}`)} />
      )}
      <NewChangeOrderDialog open={open} onOpenChange={setOpen} target={target} projectId={projectId} />
    </>
  );
}
