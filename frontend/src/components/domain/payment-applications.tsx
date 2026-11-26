"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Wallet } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Stat } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { terms } from "@/lib/region";
import type { BillingSummary, ContractListItem, PaymentApplicationDetail, PaymentApplicationSummary, Project } from "@/lib/types";

export const PAY_TONES = { draft: "neutral", submitted: "accent", certified: "warning", paid: "success" } as const;
export const PAY_STATUS: Record<string, string> = { draft: "Draft", submitted: "Submitted", certified: "Certified", paid: "Paid" };
const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const today = () => new Date().toISOString().slice(0, 10);

export function PayStatus({ a }: { a: Pick<PaymentApplicationSummary, "status" | "is_overdue"> }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Badge tone={PAY_TONES[a.status]}>{PAY_STATUS[a.status]}</Badge>
      {a.is_overdue && <Badge tone="danger">Payment overdue</Badge>}
    </span>
  );
}

export function BillingSummaryCards({ project }: { project: Project }) {
  const q = useQuery({ queryKey: ["billing-summary", project.id], queryFn: () => api<BillingSummary>(`/projects/${project.id}/billing-summary`) });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const b = q.data;
  const c = b.currency;
  const position = b.over_billed === null
    ? { value: "—", sub: b.billed_to_date === null ? "No submitted applications yet" : "Needs an approved forecast to measure earned revenue" }
    : b.over_billed !== "0.00"
      ? { value: <span className="text-warning">{formatMoney(b.over_billed, c)} over</span>, sub: `Billed ${formatMoney(b.billed_to_date, c)} vs earned ${formatMoney(b.earned_revenue, c)}` }
      : { value: <span className={cn(b.under_billed !== "0.00" && "text-accent")}>{formatMoney(b.under_billed, c)} under</span>, sub: `Billed ${formatMoney(b.billed_to_date, c)} vs earned ${formatMoney(b.earned_revenue, c)}` };
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Certified to date" value={formatMoney(b.certified_to_date, c)} sub={`Paid ${formatMoney(b.paid_to_date, c)}`} />
      <Stat label="Outstanding" value={<span className={cn(b.overdue_count > 0 && "text-danger")}>{formatMoney(b.outstanding, c)}</span>} sub={`${b.overdue_count ? `${b.overdue_count} overdue · ` : ""}Awaiting certification ${formatMoney(b.awaiting_certification, c)}`} />
      <Stat label={`${terms().retainage} held`} value={formatMoney(b.retention_held, c)} sub="On the latest application of each contract" />
      <Stat label="Billing position" value={position.value} sub={b.forecast_period && b.over_billed !== null ? `${position.sub} (forecast ${formatDate(b.forecast_period)})` : position.sub} />
    </div>
  );
}

function NewApplicationDialog({ project, open, onClose }: { project: Project; open: boolean; onClose: () => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { notify } = useToast();
  const contracts = useQuery({ queryKey: ["contracts", project.id], queryFn: () => api<ContractListItem[]>("/contracts", { query: { project_id: project.id } }), enabled: open });
  const executed = (contracts.data ?? []).filter((c) => c.status === "executed");
  const [contractId, setContractId] = useState("");
  const [periodTo, setPeriodTo] = useState(today());
  const [appDate, setAppDate] = useState(today());
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api<PaymentApplicationDetail>(`/projects/${project.id}/payment-applications`, { method: "POST", body: { contract_id: contractId || executed[0]?.id, period_to: periodTo, application_date: appDate } }),
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: ["payment-applications", project.id] });
      notify(`${a.label} started`);
      onClose();
      router.push(`/payment-applications/${a.id}`);
    },
    onError: (err) => setError(msg(err)),
  });
  const t = terms();
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title={`New ${t.payApp.toLowerCase()}`}
      description="The schedule of values is taken from the signed contract and its approved changes. Previous figures carry forward."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={create.isPending} disabled={!executed.length}
        onClick={() => { setError(null); if (!periodTo) return setError("Enter the period end date"); create.mutate(); }}>Start draft</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        {contracts.isLoading ? <Spinner /> : !executed.length ? (
          <Alert tone="warning">There is no signed (executed) prime contract on this project yet.</Alert>
        ) : (
          <>
            <Field label="Contract" required>{(p) => <Select {...p} value={contractId || executed[0]?.id} onChange={(e) => setContractId(e.target.value)}>{executed.map((c) => <option key={c.id} value={c.id}>{c.number} — {c.title}</option>)}</Select>}</Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t.payApp === "Valuation" ? "Valuation date" : "Period to"} required>{(p) => <Input {...p} type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />}</Field>
              <Field label="Application date" required>{(p) => <Input {...p} type="date" value={appDate} max={today()} onChange={(e) => setAppDate(e.target.value)} />}</Field>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}

export function PaymentApplicationsList({ project }: { project: Project }) {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["payment-applications", project.id], queryFn: () => api<PaymentApplicationSummary[]>(`/projects/${project.id}/payment-applications`) });
  const t = terms();
  const canCreate = can(P.PAYMENTS_EDIT) && !project.archived_at;
  return (
    <Card>
      <CardHeader title={t.payApps} description="Applications to the client / employer for payment against the prime contract"
        actions={canCreate ? <Button onClick={() => setOpen(true)}><Plus className="size-4" />New {t.payApp.toLowerCase()}</Button> : undefined} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? (
        <EmptyState icon={<Wallet className="size-6" />} title={`No ${t.payApps.toLowerCase()} yet`} description="Start one against a signed prime contract. Claim work by amount or percent complete, then submit, record the certificate and the payment." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">{t.payApps}</caption>
            <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
              <th className="px-4 py-2.5">Application</th><th className="px-4 py-2.5">Status</th><th className="px-4 py-2.5">Period to</th><th className="px-4 py-2.5 text-right">Applied for</th><th className="px-4 py-2.5 text-right">Certified</th><th className="px-4 py-2.5 text-right">Paid</th><th className="px-4 py-2.5 text-right">Outstanding</th><th className="px-4 py-2.5">Due</th>
            </tr></thead>
            <tbody className="num">
              {q.data.map((a) => (
                <tr key={a.id} className="border-b border-border hover:bg-surface-2/70">
                  <td className="px-4 py-2.5 font-sans"><Link className="font-medium text-accent hover:underline" href={`/payment-applications/${a.id}`}>{a.label}</Link><span className="block text-xs text-subtle">{a.contract_number} {a.contract_title}</span></td>
                  <td className="px-4 py-2.5 font-sans"><PayStatus a={a} /></td>
                  <td className="px-4 py-2.5">{formatDate(a.period_to)}</td>
                  <td className="px-4 py-2.5 text-right">{a.amount_due ? formatMoney(a.amount_due, a.currency) : <span className="text-subtle">Draft</span>}</td>
                  <td className="px-4 py-2.5 text-right">{a.certified_amount ? formatMoney(a.certified_amount, a.currency) : "—"}</td>
                  <td className="px-4 py-2.5 text-right">{a.paid_amount ? formatMoney(a.paid_amount, a.currency) : "—"}</td>
                  <td className={cn("px-4 py-2.5 text-right", a.is_overdue && "text-danger")}>{a.outstanding !== "0.00" ? formatMoney(a.outstanding, a.currency) : "—"}</td>
                  <td className="px-4 py-2.5">{formatDate(a.final_payment_date ?? a.due_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <NewApplicationDialog project={project} open={open} onClose={() => setOpen(false)} />
    </Card>
  );
}

export function PaymentsPanel({ project }: { project: Project }) {
  return (
    <div className="space-y-6">
      <BillingSummaryCards project={project} />
      <PaymentApplicationsList project={project} />
    </div>
  );
}
