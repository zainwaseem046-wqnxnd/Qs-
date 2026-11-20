"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, ListTree, Plus, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { P } from "@/lib/hooks";
import type { CostCode, CostCodeSet, CostCodeTemplate } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");

function NewSetDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: (s: CostCodeSet) => void }) {
  const { tenant } = useAuth();
  const templates = useQuery({ queryKey: ["cost-code-templates"], queryFn: () => api<CostCodeTemplate[]>("/cost-code-sets/templates") });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState("custom");
  const [levels, setLevels] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setTemplate(tenant?.tenant.country_code === "GB" ? "nrm1_elemental" : "masterformat_style");
      setLevels("");
      setError(null);
    }
  }, [open, tenant]);
  const selected = templates.data?.find((t) => t.key === template);
  const create = useMutation({
    mutationFn: () =>
      api<CostCodeSet>("/cost-code-sets", {
        method: "POST",
        body: {
          name: name.trim(),
          description: description.trim() || null,
          template_key: template,
          level_names: template === "custom" ? levels.split(">").map((l) => l.trim()).filter(Boolean) : null,
        },
      }),
    onSuccess: onCreated,
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New cost code structure" description="Use your own coding format. Templates only name the levels — you import or enter your own codes."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => { setError(null); if (name.trim().length < 2) return setError("Enter a name"); if (template === "custom" && !levels.trim()) return setError("Enter level names, e.g. Package > Trade > Item"); create.mutate(); }}>Create structure</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Name" required>{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Company elemental cost plan codes" maxLength={120} />}</Field>
        <Field label="Starting point" hint="Licensed content (e.g. RICS NRM, CSI MasterFormat) is not included; import your own codes.">
          {(p) => (
            <Select {...p} value={template} onChange={(e) => setTemplate(e.target.value)}>
              {templates.data?.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
            </Select>
          )}
        </Field>
        {template === "custom" ? (
          <Field label="Levels" hint="Separate levels with >, e.g. Package > Trade > Item" required>{(p) => <Input {...p} value={levels} onChange={(e) => setLevels(e.target.value)} />}</Field>
        ) : (
          selected && <p className="text-sm text-muted">Levels: <span className="text-fg">{selected.level_names.join(" › ")}</span></p>
        )}
        <Field label="Description">{(p) => <Textarea {...p} value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />}</Field>
      </div>
    </Dialog>
  );
}

function ImportDialog({ set, open, onOpenChange }: { set: CostCodeSet; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<{ row: number; message: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setFile(null);
      setErrors([]);
      setError(null);
    }
  }, [open]);
  const run = async () => {
    if (!file) return setError("Choose a CSV file");
    setBusy(true);
    setError(null);
    setErrors([]);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api<{ created: number; errors: { row: number; message: string }[] }>(`/cost-code-sets/${set.id}/import`, { method: "POST", body: fd });
      if (res.errors.length) setErrors(res.errors);
      else {
        await qc.invalidateQueries({ queryKey: ["cost-codes"] });
        await qc.invalidateQueries({ queryKey: ["cost-code-sets"] });
        notify(`${res.created} codes imported into ${set.name}`);
        onOpenChange(false);
      }
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={`Import codes into ${set.name}`} wide
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={run}><FileUp className="size-4" />Import</Button></>}>
      <div className="space-y-4">
        <p className="text-sm text-muted">
          CSV with a header row: <code className="font-mono text-fg">code,title,parent_code,unit</code>. <code className="font-mono">parent_code</code> and <code className="font-mono">unit</code> are optional.
          Parents can appear anywhere in the file. Nothing is imported if any row has an error.
        </p>
        <pre className="overflow-x-auto rounded-md bg-sunken p-3 text-xs">{`code,title,parent_code,unit\n2,Superstructure,,\n2.1,Frame,2,\n2.1.1,Concrete frame,2.1,m3`}</pre>
        {error && <Alert tone="danger">{error}</Alert>}
        {errors.length > 0 && (
          <Alert tone="danger" title={`${errors.length} problem${errors.length === 1 ? "" : "s"} found — nothing was imported`}>
            <ul className="mt-1 max-h-48 list-disc overflow-y-auto pl-5">
              {errors.map((e, i) => <li key={i}>Row {e.row}: {e.message}</li>)}
            </ul>
          </Alert>
        )}
        <Field label="CSV file" required>{(p) => <Input {...p} type="file" accept=".csv,text/csv" className="py-1.5" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}</Field>
      </div>
    </Dialog>
  );
}

function AddCodeDialog({ set, codes, open, onOpenChange }: { set: CostCodeSet; codes: CostCode[]; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [parent, setParent] = useState("");
  const [unit, setUnit] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setCode(""); setTitle(""); setParent(""); setUnit(""); setError(null);
    }
  }, [open]);
  const parents = codes.filter((c) => c.level < set.level_names.length);
  const parentLevel = codes.find((c) => c.id === parent)?.level ?? 0;
  const create = useMutation({
    mutationFn: () => api(`/cost-code-sets/${set.id}/codes`, { method: "POST", body: { code: code.trim(), title: title.trim(), parent_id: parent || null, unit: unit.trim() || null } }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cost-codes", set.id] });
      await qc.invalidateQueries({ queryKey: ["cost-code-sets"] });
      notify(`Code ${code.trim()} added`);
      onOpenChange(false);
    },
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Add cost code"
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => { setError(null); if (!code.trim() || !title.trim()) return setError("Code and title are required"); create.mutate(); }}>Add code</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="Parent" hint={`New code will be a ${set.level_names[parentLevel] ?? "code"}`} className="sm:col-span-2">
          {(p) => (
            <Select {...p} value={parent} onChange={(e) => setParent(e.target.value)}>
              <option value="">None (top level: {set.level_names[0]})</option>
              {parents.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Code" required>{(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} maxLength={40} className="font-mono" />}</Field>
        <Field label="Unit" hint="e.g. m², m³, SF, CY, nr, item">{(p) => <Input {...p} value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={20} />}</Field>
        <Field label="Title" required className="sm:col-span-2">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} />}</Field>
      </div>
    </Dialog>
  );
}

function SetDetail({ set }: { set: CostCodeSet }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const manage = can(P.COST_CODES_MANAGE);
  const [q, setQ] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const codes = useQuery({
    queryKey: ["cost-codes", set.id, showInactive],
    queryFn: () => api<CostCode[]>(`/cost-code-sets/${set.id}/codes`, { query: { include_inactive: showInactive } }),
  });
  const toggle = useMutation({
    mutationFn: (c: CostCode) => api(`/cost-code-sets/${set.id}/codes/${c.id}`, { method: "PATCH", body: { is_active: !c.is_active } }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["cost-codes", set.id] }); notify("Code updated"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const remove = useMutation({
    mutationFn: (c: CostCode) => api(`/cost-code-sets/${set.id}/codes/${c.id}`, { method: "DELETE" }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["cost-codes", set.id] }); await qc.invalidateQueries({ queryKey: ["cost-code-sets"] }); notify("Code deleted"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (codes.data ?? []).filter((c) => !term || c.code.toLowerCase().includes(term) || c.title.toLowerCase().includes(term));
  }, [codes.data, q]);

  return (
    <Card>
      <CardHeader
        title={set.name}
        description={<>Levels: {set.level_names.join(" › ")}{set.description ? ` · ${set.description}` : ""}</>}
        actions={manage && (
          <>
            <Button size="sm" variant="secondary" onClick={() => setImportOpen(true)}><FileUp className="size-4" />Import CSV</Button>
            <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="size-4" />Add code</Button>
          </>
        )}
      />
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search code or title" className="pl-9" aria-label="Search codes" />
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--accent)]" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />Show inactive</label>
      </div>
      {codes.isLoading ? <Spinner /> : codes.error ? <ErrorState error={codes.error} /> : filtered.length === 0 ? (
        <EmptyState icon={<ListTree className="size-6" />} title={q ? "No codes match" : "No codes yet"} description="Import your codes from a CSV file or add them one by one." />
      ) : (
        <ul className="divide-y divide-border">
          {filtered.map((c) => (
            <li key={c.id} className={cn("flex items-center gap-3 px-5 py-2.5", !c.is_active && "opacity-60")}>
              <span className="min-w-0 flex-1" style={{ paddingLeft: `${(c.level - 1) * 1.25}rem` }}>
                <span className="font-mono text-sm font-medium">{c.code}</span>
                <span className={cn("ml-3 text-sm", c.level === 1 && "font-semibold")}>{c.title}</span>
                {c.unit && <span className="ml-2 text-xs text-subtle">({c.unit})</span>}
              </span>
              <span className="hidden text-xs text-subtle sm:inline">{set.level_names[c.level - 1]}</span>
              {!c.is_active && <Badge>Inactive</Badge>}
              {manage && (
                <>
                  <Button size="sm" variant="ghost" onClick={() => toggle.mutate(c)}>{c.is_active ? "Deactivate" : "Activate"}</Button>
                  <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Delete ${c.code}?`} description="Codes used by estimates or budgets, or with child codes, cannot be deleted — deactivate them instead." confirmLabel="Delete" onConfirm={() => remove.mutateAsync(c)} />
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <AddCodeDialog set={set} codes={codes.data ?? []} open={addOpen} onOpenChange={setAddOpen} />
      <ImportDialog set={set} open={importOpen} onOpenChange={setImportOpen} />
    </Card>
  );
}

export default function CostCodesPage() {
  const { can, tenant } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const [selected, setSelected] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const allowed = can(P.ESTIMATES_VIEW) || can(P.BUDGETS_VIEW) || can(P.COST_CODES_MANAGE);
  const sets = useQuery({ queryKey: ["cost-code-sets"], queryFn: () => api<CostCodeSet[]>("/cost-code-sets"), enabled: allowed });
  useEffect(() => {
    if (!selected && sets.data?.[0]) setSelected(sets.data[0].id);
  }, [sets.data, selected]);

  if (tenant && !allowed) return <Alert tone="warning">Your role cannot view cost codes.</Alert>;
  const current = sets.data?.find((s) => s.id === selected);
  return (
    <>
      <PageHeader
        title="Cost Codes"
        description="Your organization's own cost coding structures, used by estimates and budgets."
        actions={can(P.COST_CODES_MANAGE) && <Button onClick={() => setNewOpen(true)}><Plus className="size-4" />New structure</Button>}
      />
      {sets.isLoading ? <Spinner /> : sets.error ? <ErrorState error={sets.error} /> : !sets.data?.length ? (
        <Card><EmptyState icon={<ListTree className="size-6" />} title="No cost code structures yet" description="Create a structure in your own format, then import your codes from CSV." /></Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
          <Card className="h-fit">
            <ul className="divide-y divide-border" aria-label="Cost code structures">
              {sets.data.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => setSelected(s.id)} aria-current={s.id === selected ? "true" : undefined}
                    className={cn("w-full px-4 py-3 text-left hover:bg-surface-2", s.id === selected && "bg-accent-soft")}>
                    <p className="text-sm font-medium">{s.name}</p>
                    <p className="text-xs text-subtle">{s.code_count} codes · {s.level_names.length} levels</p>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          {current && <SetDetail key={current.id} set={current} />}
        </div>
      )}
      <NewSetDialog open={newOpen} onOpenChange={setNewOpen} onCreated={async (s) => { await qc.invalidateQueries({ queryKey: ["cost-code-sets"] }); setSelected(s.id); setNewOpen(false); notify(`${s.name} created`); }} />
    </>
  );
}
