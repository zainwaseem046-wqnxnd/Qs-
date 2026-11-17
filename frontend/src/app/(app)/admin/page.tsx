"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { ActivityList } from "@/components/domain/activity";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { Pagination } from "@/components/ui/table";
import { TabPanel, Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, P, useVocabulary } from "@/lib/hooks";
import type { AuditEvent, Invitation, Member, Page, PermissionDef, Role, Tenant } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");

function OrganizationSettings() {
  const { tenant, can } = useAuth();
  const vocab = useVocabulary().data;
  const qc = useQueryClient();
  const { notify } = useToast();
  const t = tenant?.tenant;
  const [name, setName] = useState(t?.name ?? "");
  const [state, setState] = useState(t?.home_state ?? "");
  const [currency, setCurrency] = useState(t?.default_currency ?? "USD");
  const [tz, setTz] = useState(t?.timezone ?? "America/New_York");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api<Tenant>("/tenant", { method: "PATCH", body: { name: name.trim(), home_state: state || null, default_currency: currency, timezone: tz } }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["tenant"] }); notify("Organization settings saved"); setError(null); },
    onError: (err) => setError(msg(err)),
  });
  const editable = can(P.TENANT_MANAGE);
  const zones = ["America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu", "America/Puerto_Rico"];
  return (
    <Card>
      <CardHeader title="Organization" description={`Identifier: ${t?.slug ?? ""}`} />
      <CardBody>
        <form className="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (name.trim().length < 2) return setError("Enter the organization name"); save.mutate(); }}>
          {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
          <Field label="Organization name" required className="sm:col-span-2">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} disabled={!editable} />}</Field>
          <Field label="Home state">{(p) => <Select {...p} value={state} onChange={(e) => setState(e.target.value)} disabled={!editable}><Options map={vocab?.us_states} placeholder="—" /></Select>}</Field>
          <Field label="Default currency">{(p) => <Select {...p} value={currency} onChange={(e) => setCurrency(e.target.value)} disabled={!editable}>{(vocab?.currencies ?? ["USD"]).map((c) => <option key={c}>{c}</option>)}</Select>}</Field>
          <Field label="Time zone">{(p) => <Select {...p} value={tz} onChange={(e) => setTz(e.target.value)} disabled={!editable}>{zones.map((z) => <option key={z}>{z}</option>)}</Select>}</Field>
          <Field label="Measurement system" hint="Imperial (US customary) units">{(p) => <Input {...p} value="US customary" disabled />}</Field>
          {editable && <div className="sm:col-span-2"><Button type="submit" loading={save.isPending}>Save settings</Button></div>}
        </form>
      </CardBody>
    </Card>
  );
}

function Members() {
  const { can, session, tenant } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const manage = can(P.MEMBERS_MANAGE);
  const members = useQuery({ queryKey: ["tenant-members"], queryFn: () => api<Member[]>("/tenant/members") });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/tenant/roles") });
  const update = useMutation({
    mutationFn: (v: { id: string; body: Record<string, unknown> }) => api(`/tenant/members/${v.id}`, { method: "PATCH", body: v.body }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["tenant-members"] }); notify("Member updated"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/tenant/members/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["tenant-members"] }); notify("Member removed"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  if (members.isLoading) return <Spinner />;
  if (members.error) return <ErrorState error={members.error} />;
  const assignable = (roles.data ?? []).filter((r) => r.key !== "owner" || tenant?.role.key === "owner");
  return (
    <Card>
      <CardHeader title="Members" description={`${members.data?.length ?? 0} people in this organization`} />
      <ul className="divide-y divide-border">
        {members.data?.map((m) => {
          const self = m.user_id === session?.user.id;
          return (
            <li key={m.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{m.full_name}{self && <span className="ml-2 text-xs text-subtle">(you)</span>}</p>
                <p className="text-xs text-subtle">{m.email} · joined {formatDate(m.created_at)}</p>
              </div>
              {m.mfa_enabled ? <Badge tone="success"><ShieldCheck className="size-3" />2FA</Badge> : <Badge>No 2FA</Badge>}
              {m.status !== "active" && <StatusBadge status={m.status} />}
              {manage && !self ? (
                <>
                  <Select className="w-48" value={m.role.id} aria-label={`Role for ${m.full_name}`} onChange={(e) => update.mutate({ id: m.id, body: { role_id: e.target.value } })}>
                    {assignable.concat(assignable.some((r) => r.id === m.role.id) ? [] : [{ ...m.role, description: null, is_system: true, permission_keys: [], member_count: 0 }]).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                  </Select>
                  <Button size="sm" variant="secondary" onClick={() => update.mutate({ id: m.id, body: { status: m.status === "active" ? "suspended" : "active" } })}>
                    {m.status === "active" ? "Suspend" : "Reactivate"}
                  </Button>
                  <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Remove ${m.full_name}?`} description="They immediately lose access to this organization." confirmLabel="Remove member" onConfirm={() => remove.mutateAsync(m.id)} />
                </>
              ) : (
                <Badge tone="accent">{m.role.name}</Badge>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Invitations() {
  const { tenant } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const invites = useQuery({ queryKey: ["invitations"], queryFn: () => api<Invitation[]>("/tenant/invitations") });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/tenant/roles") });
  const create = useMutation({
    mutationFn: () => api<Invitation>("/tenant/invitations", { method: "POST", body: { email: email.trim(), role_id: roleId } }),
    onSuccess: async (inv) => { setCreated(inv); await qc.invalidateQueries({ queryKey: ["invitations"] }); },
    onError: (err) => setError(msg(err)),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/tenant/invitations/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["invitations"] }); notify("Invitation revoked"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const assignable = (roles.data ?? []).filter((r) => r.key !== "owner" || tenant?.role.key === "owner");
  const reset = () => { setEmail(""); setRoleId(assignable.find((r) => r.key === "project_manager")?.id ?? ""); setError(null); setCreated(null); setCopied(false); };
  return (
    <Card>
      <CardHeader title="Invitations" description="Invite colleagues by email. Links expire after 7 days and work once." actions={<Button size="sm" onClick={() => { reset(); setOpen(true); }}><Plus className="size-4" />Invite</Button>} />
      {invites.isLoading ? <Spinner /> : invites.data?.length === 0 ? <p className="px-5 py-6 text-sm text-muted">No invitations sent yet.</p> : (
        <ul className="divide-y divide-border">
          {invites.data?.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{i.email}</p>
                <p className="text-xs text-subtle">{i.role.name} · sent {formatDate(i.created_at)} · expires {formatDate(i.expires_at)}</p>
              </div>
              <StatusBadge status={i.status} />
              {i.status === "pending" && <ConfirmButton label="Revoke" title={`Revoke invitation for ${i.email}?`} description="The link will stop working immediately." confirmLabel="Revoke" onConfirm={() => revoke.mutateAsync(i.id)} />}
            </li>
          ))}
        </ul>
      )}
      <Dialog open={open} onOpenChange={setOpen} title={created ? "Invitation created" : "Invite a team member"}
        footer={created ? <Button onClick={() => setOpen(false)}>Done</Button> : <><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => { setError(null); if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) return setError("Enter a valid email address"); if (!roleId) return setError("Choose a role"); create.mutate(); }}>Create invitation</Button></>}>
        {created ? (
          <div className="space-y-3">
            <Alert tone="info" title="Email delivery is not configured yet">Copy this one-time link and send it to {created.email} securely. It is shown only once.</Alert>
            <div className="flex gap-2">
              <Input readOnly value={created.accept_url ?? ""} aria-label="Invitation link" onFocus={(e) => e.currentTarget.select()} />
              <Button variant="secondary" onClick={async () => { await navigator.clipboard.writeText(created.accept_url ?? ""); setCopied(true); }}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}{copied ? "Copied" : "Copy"}</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {error && <Alert tone="danger">{error}</Alert>}
            <Field label="Email" required>{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />}</Field>
            <Field label="Role" required>{(p) => <Select {...p} value={roleId} onChange={(e) => setRoleId(e.target.value)}><option value="">Select a role…</option>{assignable.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>}</Field>
          </div>
        )}
      </Dialog>
    </Card>
  );
}

function Roles() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/tenant/roles") });
  const perms = useQuery({ queryKey: ["permissions"], queryFn: () => api<PermissionDef[]>("/tenant/permissions") });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), description: description.trim() || null, permissions: [...selected] };
      return editing ? api(`/tenant/roles/${editing.id}`, { method: "PATCH", body }) : api("/tenant/roles", { method: "POST", body });
    },
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["roles"] }); notify(editing ? "Role updated" : "Role created"); setOpen(false); },
    onError: (err) => setError(msg(err)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/tenant/roles/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["roles"] }); notify("Role deleted"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  if (roles.isLoading || perms.isLoading) return <Spinner />;
  const manage = can(P.ROLES_MANAGE);
  const openEditor = (r: Role | null) => { setEditing(r); setName(r?.name ?? ""); setDescription(r?.description ?? ""); setSelected(new Set(r?.permission_keys ?? [])); setError(null); setOpen(true); };
  const byCategory = (perms.data ?? []).reduce<Record<string, PermissionDef[]>>((acc, p) => ((acc[p.category] ??= []).push(p), acc), {});
  return (
    <Card>
      <CardHeader title="Roles & permissions" description="System roles are fixed. Custom roles can only grant permissions you hold." actions={manage && <Button size="sm" onClick={() => openEditor(null)}><Plus className="size-4" />Custom role</Button>} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Permission matrix</caption>
          <thead>
            <tr className="border-b border-border bg-surface-2/60">
              <th scope="col" className="sticky left-0 bg-surface-2 px-4 py-2 text-left text-xs font-semibold uppercase text-subtle">Permission</th>
              {roles.data?.map((r) => (
                <th key={r.id} scope="col" className="px-3 py-2 text-center text-xs font-semibold text-subtle">
                  {manage && !r.is_system ? <button type="button" className="text-accent hover:underline" onClick={() => openEditor(r)}>{r.name}</button> : r.name}
                  <span className="block font-normal">{r.member_count} member{r.member_count === 1 ? "" : "s"}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perms.data?.map((p) => (
              <tr key={p.key} className="border-b border-border last:border-0">
                <th scope="row" className="sticky left-0 bg-surface px-4 py-2 text-left font-normal"><span className="font-medium">{p.description}</span><span className="block font-mono text-xs text-subtle">{p.key}</span></th>
                {roles.data?.map((r) => (
                  <td key={r.id} className="px-3 py-2 text-center">{r.permission_keys.includes(p.key) ? <Check className="mx-auto size-4 text-success" aria-label="Granted" /> : <span className="text-subtle" aria-label="Not granted">·</span>}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Dialog open={open} onOpenChange={setOpen} title={editing ? `Edit role: ${editing.name}` : "Create custom role"} wide
        footer={<>{editing && <ConfirmButton label="Delete role" title={`Delete ${editing.name}?`} description="Only roles with no members or pending invitations can be deleted." confirmLabel="Delete" onConfirm={async () => { await remove.mutateAsync(editing.id); setOpen(false); }} />}<div className="flex-1" /><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={save.isPending} onClick={() => { setError(null); if (name.trim().length < 2) return setError("Enter a role name"); if (selected.size === 0) return setError("Select at least one permission"); save.mutate(); }}>Save role</Button></>}>
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Role name" required>{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />}</Field>
          <Field label="Description">{(p) => <Textarea {...p} value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={500} />}</Field>
          {Object.entries(byCategory).map(([cat, list]) => (
            <fieldset key={cat}>
              <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">{cat}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {list.map((p) => (
                  <label key={p.key} className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-0.5 size-4 accent-[var(--accent)]" checked={selected.has(p.key)} onChange={(e) => { const next = new Set(selected); if (e.target.checked) next.add(p.key); else next.delete(p.key); setSelected(next); }} />
                    {p.description}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
      </Dialog>
    </Card>
  );
}

function AuditLog() {
  const [offset, setOffset] = useState(0);
  const [entity, setEntity] = useState("");
  const q = useQuery({ queryKey: ["audit", offset, entity], queryFn: () => api<Page<AuditEvent>>("/audit-events", { query: { limit: 50, offset, entity_type: entity } }) });
  return (
    <Card>
      <CardHeader title="Audit log" description="Append-only record of every change in this organization. It cannot be edited or deleted."
        actions={<Select className="w-44" value={entity} onChange={(e) => { setEntity(e.target.value); setOffset(0); }} aria-label="Filter by record type"><option value="">All records</option>{["project", "project_member", "project_party", "project_phase", "company", "contact", "document", "membership", "invitation", "role", "tenant"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</Select>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : q.data && <><ActivityList events={q.data.items} /><Pagination total={q.data.total} limit={50} offset={offset} onChange={setOffset} /></>}
    </Card>
  );
}

export default function AdminPage() {
  const { can, tenant } = useAuth();
  const [tab, setTab] = useState("organization");
  if (!tenant) return <Spinner />;
  const tabs = [
    { value: "organization", label: "Organization", show: true },
    { value: "members", label: "Members", show: can(P.MEMBERS_VIEW) },
    { value: "invitations", label: "Invitations", show: can(P.MEMBERS_MANAGE) },
    { value: "roles", label: "Roles & permissions", show: can(P.MEMBERS_VIEW) },
    { value: "audit", label: "Audit log", show: can(P.AUDIT_VIEW) },
  ].filter((t) => t.show);
  return (
    <>
      <PageHeader title="Administration" description="Organization settings, people, access control and audit history." />
      <Tabs value={tab} onValueChange={setTab} tabs={tabs}>
        <div className="pt-6">
          <TabPanel value="organization"><OrganizationSettings /></TabPanel>
          <TabPanel value="members"><Members /></TabPanel>
          <TabPanel value="invitations"><Invitations /></TabPanel>
          <TabPanel value="roles"><Roles /></TabPanel>
          <TabPanel value="audit"><AuditLog /></TabPanel>
        </div>
      </Tabs>
    </>
  );
}
