"use client";

import { useQuery } from "@tanstack/react-query";
import { Calculator, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { DataTable, type Column } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import type { CostCodeSet, Estimate, Page, ProjectListItem } from "@/lib/types";

export const ESTIMATE_TYPES: Record<string, string> = {
  conceptual: "Conceptual / order of magnitude",
  cost_plan: "Cost plan",
  detailed: "Detailed estimate",
  pre_tender: "Pre-tender estimate",
  tender: "Tender / bid",
};

export function NewEstimateDialog({ open, onOpenChange, projectId }: { open: boolean; onOpenChange: (o: boolean) => void; projectId?: string }) {
  const router = useRouter();
  const { tenant } = useAuth();
  const [project, setProject] = useState(projectId ?? "");
  const [name, setName] = useState("");
  const [type, setType] = useState("detailed");
  const [setId, setSetId] = useState("");
  const [baseDate, setBaseDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const projects = useQuery({
    queryKey: ["projects", "picker"],
    queryFn: () => api<Page<ProjectListItem>>("/projects", { query: { limit: 200, sort: "name", order: "asc" } }),
    enabled: open && !projectId,
  });
  const sets = useQuery({ queryKey: ["cost-code-sets"], queryFn: () => api<CostCodeSet[]>("/cost-code-sets"), enabled: open });
  useEffect(() => {
    if (open) {
      setProject(projectId ?? "");
      setName("");
      setType(tenant?.tenant.country_code === "GB" ? "cost_plan" : "detailed");
      setBaseDate("");
      setError(null);
    }
  }, [open, projectId, tenant]);
  useEffect(() => {
    if (open && !setId && sets.data?.[0]) setSetId(sets.data[0].id);
  }, [open, sets.data, setId]);
  const submit = async () => {
    setError(null);
    if (!project) return setError("Choose a project");
    if (name.trim().length < 2) return setError("Enter an estimate name");
    setBusy(true);
    try {
      const est = await api<Estimate>(`/projects/${project}/estimates`, {
        method: "POST",
        body: { name: name.trim(), estimate_type: type, cost_code_set_id: setId || null, price_base_date: baseDate || null },
      });
      router.push(`/estimates/${est.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create the estimate");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New estimate"
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={submit}>Create estimate</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        {!projectId && (
          <Field label="Project" required>
            {(p) => (
              <Select {...p} value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">Select a project…</option>
                {projects.data?.items.map((pr) => <option key={pr.id} value={pr.id}>{pr.number} — {pr.name}</option>)}
              </Select>
            )}
          </Field>
        )}
        <Field label="Name" required>{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} placeholder="Stage 3 cost plan" />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type">{(p) => <Select {...p} value={type} onChange={(e) => setType(e.target.value)}>{Object.entries(ESTIMATE_TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select>}</Field>
          <Field label="Price base date" hint="Date the rates are priced at">{(p) => <Input {...p} type="date" value={baseDate} onChange={(e) => setBaseDate(e.target.value)} />}</Field>
        </div>
        <Field label="Cost code structure" hint={sets.data?.length ? undefined : "No structures yet — lines will be unassigned. Create one under Cost Codes."}>
          {(p) => (
            <Select {...p} value={setId} onChange={(e) => setSetId(e.target.value)}>
              <option value="">None</option>
              {sets.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          )}
        </Field>
      </div>
    </Dialog>
  );
}

export function EstimatesList({ projectId, canCreate }: { projectId?: string; canCreate?: boolean }) {
  const router = useRouter();
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["estimates", projectId ?? "all"], queryFn: () => api<Estimate[]>("/estimates", { query: { project_id: projectId } }) });
  const columns: Column<Estimate>[] = [
    { key: "name", header: "Estimate", cell: (e) => <div className="min-w-48"><p className="font-medium">{e.name}</p><p className="text-xs text-subtle">{ESTIMATE_TYPES[e.estimate_type] ?? e.estimate_type}</p></div> },
    ...(projectId ? [] : [{ key: "project", header: "Project", cell: (e: Estimate) => <span className="text-muted">{e.project_number} — {e.project_name}</span> }]),
    {
      key: "version",
      header: "Latest version",
      cell: (e) => {
        const v = e.versions[e.versions.length - 1];
        return v ? <span className="flex items-center gap-2">v{v.version_number}<StatusBadge status={v.status === "approved" ? "accepted" : v.status === "issued" ? "pending" : "planned"} label={v.status} /></span> : "—";
      },
    },
    {
      key: "total",
      header: "Latest issued total",
      align: "right",
      cell: (e) => {
        const v = [...e.versions].reverse().find((x) => x.total);
        return v ? formatMoney(v.total, e.currency) : <span className="text-subtle">Not issued</span>;
      },
    },
    { key: "updated", header: "Updated", cell: (e) => <span className="num text-muted">{formatDate(e.updated_at)}</span> },
  ];
  return (
    <>
      {(canCreate ?? true) && can(P.ESTIMATES_EDIT) && (
        <div className="flex justify-end border-b border-border p-4">
          <Button onClick={() => setOpen(true)}><Plus className="size-4" />New estimate</Button>
        </div>
      )}
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? (
        <EmptyState icon={<Calculator className="size-6" />} title="No estimates yet" description="Create an estimate or cost plan, price it line by line, then issue and approve it." />
      ) : (
        <DataTable caption="Estimates" columns={columns} rows={q.data} rowKey={(e) => e.id} onRowClick={(e) => router.push(`/estimates/${e.id}`)} />
      )}
      <NewEstimateDialog open={open} onOpenChange={setOpen} projectId={projectId} />
    </>
  );
}
