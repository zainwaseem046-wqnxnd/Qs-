"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ActivityList } from "@/components/domain/activity";
import { BudgetPanel } from "@/components/domain/budget-panel";
import { DocumentsPanel } from "@/components/domain/documents-panel";
import { EstimatesList } from "@/components/domain/estimates-list";
import { ProjectForm } from "@/components/domain/project-form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, DescriptionList } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Options, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { Pagination } from "@/components/ui/table";
import { TabPanel, Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, label, P, useVocabulary } from "@/lib/hooks";
import { formatMoney, formatPercent } from "@/lib/money";
import { terms } from "@/lib/region";
import type { AuditEvent, Company, Member, Page, Project, ProjectMember, ProjectParty, ProjectPhase } from "@/lib/types";

function useInvalidate(projectId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["project", projectId] });
}

function errorMessage(err: unknown) {
  return err instanceof ApiError ? err.message : "Something went wrong";
}

function Overview({ project, onEdit }: { project: Project; onEdit: () => void }) {
  const vocab = useVocabulary().data;
  const a = project.site_address;
  const address = a ? [a.line1, [a.city, a.state_code].filter(Boolean).join(", "), a.postal_code].filter(Boolean).join(" · ") : "—";
  const restricted = (
    <span className="inline-flex items-center gap-1 text-muted">
      <Lock className="size-3.5" />Restricted
    </span>
  );
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <Card className="xl:col-span-2">
        <CardHeader title="Project details" actions={project.can_edit && <Button size="sm" variant="secondary" onClick={onEdit}><Pencil className="size-4" />Edit</Button>} />
        <CardBody>
          <DescriptionList
            items={[
              { label: "Sector", value: label(vocab?.sectors, project.sector) },
              { label: "Project type", value: project.project_type ?? "—" },
              { label: "Our role", value: label(vocab?.our_roles, project.our_role) },
              { label: "Delivery method", value: label(vocab?.delivery_methods, project.delivery_method) },
              { label: "Contract type", value: label(vocab?.contract_types, project.contract_type) },
              { label: "Client / owner", value: project.client_company ? <Link className="text-accent hover:underline" href={`/directory/${project.client_company.id}`}>{project.client_company.name}</Link> : "—" },
              { label: "Site", value: address },
              { label: "County", value: a?.county ?? "—" },
              { label: "Public works", value: project.is_public_works ? "Yes" : "No" },
              ...(terms().usesStates ? [{ label: "Prevailing wage", value: project.prevailing_wage ? "Yes" : "No" }] : []),
              { label: "Reporting period ends", value: project.reporting_period_end_day === 31 ? "Month end" : `Day ${project.reporting_period_end_day}` },
              { label: "Currency", value: project.currency },
            ]}
          />
          {project.description && <p className="mt-6 whitespace-pre-wrap border-t border-border pt-4 text-sm text-muted">{project.description}</p>}
        </CardBody>
      </Card>
      <div className="space-y-6">
        <Card>
          <CardHeader title="Contract" />
          <CardBody>
            <DescriptionList
              columns={1}
              items={[
                { label: "Original contract value", value: project.financials_visible ? <span className="num whitespace-nowrap text-lg font-semibold">{formatMoney(project.original_contract_value, project.currency)}</span> : restricted },
                { label: terms().retainage, value: project.financials_visible ? formatPercent(project.retainage_percent) : restricted },
              ]}
            />
            <p className="mt-4 text-xs text-subtle">Revised contract value, budgets and forecasts are calculated from change orders and cost records in Phase 2.</p>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Schedule" />
          <CardBody>
            <DescriptionList
              columns={1}
              items={[
                { label: "Start", value: formatDate(project.start_date) },
                { label: "Planned completion", value: formatDate(project.planned_completion_date) },
                { label: "Actual completion", value: formatDate(project.actual_completion_date) },
              ]}
            />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function Team({ project }: { project: Project }) {
  const vocab = useVocabulary().data;
  const { can } = useAuth();
  const { notify } = useToast();
  const invalidate = useInvalidate(project.id);
  const manage = can(P.PROJECTS_MEMBERS_MANAGE) && !project.archived_at;
  const [open, setOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("project_engineer");
  const [error, setError] = useState<string | null>(null);

  const members = useQuery({ queryKey: ["project", project.id, "members"], queryFn: () => api<ProjectMember[]>(`/projects/${project.id}/members`) });
  const orgMembers = useQuery({ queryKey: ["tenant-members"], queryFn: () => api<Member[]>("/tenant/members"), enabled: open && can(P.MEMBERS_VIEW) });

  const add = useMutation({
    mutationFn: () => api(`/projects/${project.id}/members`, { method: "POST", body: { user_id: userId, project_role: role } }),
    onSuccess: async () => {
      await invalidate();
      notify("Team member added");
      setOpen(false);
    },
    onError: (err) => setError(errorMessage(err)),
  });
  const update = useMutation({
    mutationFn: (v: { id: string; role: string }) => api(`/projects/${project.id}/members/${v.id}`, { method: "PATCH", body: { project_role: v.role } }),
    onSuccess: async () => { await invalidate(); notify("Project role updated"); },
    onError: (err) => notify(errorMessage(err), "danger"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/projects/${project.id}/members/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await invalidate(); notify("Team member removed"); },
    onError: (err) => notify(errorMessage(err), "danger"),
  });

  const existing = new Set(members.data?.map((m) => m.user_id));
  const candidates = orgMembers.data?.filter((m) => m.status === "active" && !existing.has(m.user_id)) ?? [];

  return (
    <Card>
      <CardHeader
        title="Project team"
        description="Members can see this project even without portfolio-wide access."
        actions={manage && <Button size="sm" onClick={() => { setError(null); setUserId(""); setOpen(true); }}><Plus className="size-4" />Add member</Button>}
      />
      {members.isLoading ? <Spinner /> : members.error ? <ErrorState error={members.error} /> : (
        <ul className="divide-y divide-border">
          {members.data?.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{m.full_name}</p>
                <p className="text-xs text-subtle">{m.email}</p>
              </div>
              {manage ? (
                <Select className="w-56" value={m.project_role} aria-label={`Project role for ${m.full_name}`} onChange={(e) => update.mutate({ id: m.id, role: e.target.value })}>
                  <Options map={vocab?.project_member_roles} />
                </Select>
              ) : (
                <Badge>{label(vocab?.project_member_roles, m.project_role)}</Badge>
              )}
              {manage && (
                <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Remove ${m.full_name} from the team?`} description="They will lose access to this project unless they can view all projects." confirmLabel="Remove" onConfirm={() => remove.mutateAsync(m.id)} />
              )}
            </li>
          ))}
        </ul>
      )}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Add team member"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={!userId} loading={add.isPending} onClick={() => add.mutate()}>Add to team</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          {!can(P.MEMBERS_VIEW) ? (
            <Alert tone="warning">Your role cannot view the organization member list.</Alert>
          ) : candidates.length === 0 && !orgMembers.isLoading ? (
            <Alert tone="info">Everyone in the organization is already on this team. Invite more people from Administration.</Alert>
          ) : (
            <Field label="Person" required>
              {(p) => (
                <Select {...p} value={userId} onChange={(e) => setUserId(e.target.value)}>
                  <option value="">Select a member…</option>
                  {candidates.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name} — {m.role.name}</option>)}
                </Select>
              )}
            </Field>
          )}
          <Field label="Project role" required>
            {(p) => <Select {...p} value={role} onChange={(e) => setRole(e.target.value)}><Options map={vocab?.project_member_roles} /></Select>}
          </Field>
        </div>
      </Dialog>
    </Card>
  );
}

function Parties({ project }: { project: Project }) {
  const vocab = useVocabulary().data;
  const { can } = useAuth();
  const { notify } = useToast();
  const invalidate = useInvalidate(project.id);
  const edit = project.can_edit;
  const [open, setOpen] = useState(false);
  const [companyId, setCompanyId] = useState("");
  const [role, setRole] = useState("architect");
  const [error, setError] = useState<string | null>(null);
  const parties = useQuery({ queryKey: ["project", project.id, "parties"], queryFn: () => api<ProjectParty[]>(`/projects/${project.id}/parties`) });
  const companies = useQuery({ queryKey: ["companies", "all-active"], queryFn: () => api<Page<Company>>("/companies", { query: { limit: 200 } }), enabled: open });
  const add = useMutation({
    mutationFn: () => api(`/projects/${project.id}/parties`, { method: "POST", body: { company_id: companyId, party_role: role } }),
    onSuccess: async () => { await invalidate(); notify("Company added to project"); setOpen(false); },
    onError: (err) => setError(errorMessage(err)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/projects/${project.id}/parties/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await invalidate(); notify("Company removed from project"); },
    onError: (err) => notify(errorMessage(err), "danger"),
  });
  return (
    <Card>
      <CardHeader
        title="Project parties"
        description="Owner, design team, consultants and key trade partners."
        actions={edit && can(P.COMPANIES_VIEW) && <Button size="sm" onClick={() => { setError(null); setCompanyId(""); setOpen(true); }}><Plus className="size-4" />Add company</Button>}
      />
      {parties.isLoading ? <Spinner /> : parties.data?.length === 0 ? (
        <EmptyState title="No companies linked yet" description="Link architects, engineers, owners and subcontractors from your directory." />
      ) : (
        <ul className="divide-y divide-border">
          {parties.data?.map((pt) => (
            <li key={pt.id} className="flex items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <Link href={`/directory/${pt.company.id}`} className="text-sm font-medium hover:underline">{pt.company.name}</Link>
                <p className="text-xs text-subtle">{label(vocab?.company_types, pt.company.company_type)}</p>
              </div>
              <Badge tone="accent">{label(vocab?.party_roles, pt.party_role)}</Badge>
              {edit && <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Remove ${pt.company.name}?`} description={`Removes the ${label(vocab?.party_roles, pt.party_role)} role from this project.`} confirmLabel="Remove" onConfirm={() => remove.mutateAsync(pt.id)} />}
            </li>
          ))}
        </ul>
      )}
      <Dialog open={open} onOpenChange={setOpen} title="Add company to project"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={!companyId} loading={add.isPending} onClick={() => add.mutate()}>Add</Button></>}>
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Company" hint="Not listed? Add it in the Directory first." required>
            {(p) => (
              <Select {...p} value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
                <option value="">Select a company…</option>
                {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Role on project" required>
            {(p) => <Select {...p} value={role} onChange={(e) => setRole(e.target.value)}><Options map={vocab?.party_roles} /></Select>}
          </Field>
        </div>
      </Dialog>
    </Card>
  );
}

function Phases({ project }: { project: Project }) {
  const vocab = useVocabulary().data;
  const { notify } = useToast();
  const invalidate = useInvalidate(project.id);
  const edit = project.can_edit;
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const phases = useQuery({ queryKey: ["project", project.id, "phases"], queryFn: () => api<ProjectPhase[]>(`/projects/${project.id}/phases`) });
  const add = useMutation({
    mutationFn: () => api(`/projects/${project.id}/phases`, { method: "POST", body: { name: name.trim(), start_date: start || null, end_date: end || null } }),
    onSuccess: async () => { await invalidate(); setName(""); setStart(""); setEnd(""); notify("Phase added"); },
    onError: (err) => setError(errorMessage(err)),
  });
  const update = useMutation({
    mutationFn: (ph: ProjectPhase) => api(`/projects/${project.id}/phases/${ph.id}`, { method: "PUT", body: { name: ph.name, status: ph.status, start_date: ph.start_date, end_date: ph.end_date } }),
    onSuccess: () => invalidate(),
    onError: (err) => notify(errorMessage(err), "danger"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/projects/${project.id}/phases/${id}`, { method: "DELETE" }),
    onSuccess: async () => { await invalidate(); notify("Phase deleted"); },
    onError: (err) => notify(errorMessage(err), "danger"),
  });
  return (
    <Card>
      <CardHeader title="Project phases" description="Sequence the work for reporting (e.g. Sitework, Structure, Envelope, Interiors)." />
      {phases.isLoading ? <Spinner /> : (
        <ol className="divide-y divide-border">
          {phases.data?.length === 0 && <li className="px-5 py-4 text-sm text-muted">No phases defined.</li>}
          {phases.data?.map((ph) => (
            <li key={ph.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <span className="num w-6 text-sm text-subtle">{ph.sequence}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{ph.name}</p>
                <p className="num text-xs text-subtle">{formatDate(ph.start_date)} – {formatDate(ph.end_date)}</p>
              </div>
              {edit ? (
                <Select className="w-40" value={ph.status} aria-label={`Status of ${ph.name}`} onChange={(e) => update.mutate({ ...ph, status: e.target.value })}>
                  <Options map={vocab?.phase_statuses} />
                </Select>
              ) : <StatusBadge status={ph.status} label={label(vocab?.phase_statuses, ph.status)} />}
              {edit && <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Delete phase “${ph.name}”?`} description="This removes the phase from the project." confirmLabel="Delete" onConfirm={() => remove.mutateAsync(ph.id)} />}
            </li>
          ))}
        </ol>
      )}
      {edit && (
        <form
          className="grid grid-cols-1 items-end gap-3 border-t border-border px-5 py-4 sm:grid-cols-[1fr_10rem_10rem_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            if (!name.trim()) return setError("Enter a phase name");
            if (start && end && end < start) return setError("End date must be on or after the start date");
            add.mutate();
          }}
        >
          <Field label="New phase">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="Sitework" />}</Field>
          <Field label="Start">{(p) => <Input {...p} type="date" value={start} onChange={(e) => setStart(e.target.value)} />}</Field>
          <Field label="End">{(p) => <Input {...p} type="date" value={end} onChange={(e) => setEnd(e.target.value)} />}</Field>
          <Button type="submit" loading={add.isPending}><Plus className="size-4" />Add</Button>
          {error && <p role="alert" className="text-sm text-danger sm:col-span-4">{error}</p>}
        </form>
      )}
    </Card>
  );
}

function Activity({ project }: { project: Project }) {
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ["project", project.id, "activity", offset],
    queryFn: () => api<Page<AuditEvent>>(`/projects/${project.id}/activity`, { query: { limit: 25, offset } }),
  });
  return (
    <Card>
      <CardHeader title="Activity" description="Immutable audit trail of every change to this project." />
      {q.isLoading ? <Spinner /> : q.data && (
        <>
          <ActivityList events={q.data.items} />
          <Pagination total={q.data.total} limit={25} offset={offset} onChange={setOffset} />
        </>
      )}
    </Card>
  );
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const vocab = useVocabulary().data;
  const { can } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const q = useQuery({ queryKey: ["project", id], queryFn: () => api<Project>(`/projects/${id}`) });
  const archive = useMutation({
    mutationFn: (archived: boolean) => api<Project>(`/projects/${id}/${archived ? "archive" : "restore"}`, { method: "POST" }),
    onSuccess: (p) => {
      qc.setQueryData(["project", id], p);
      void qc.invalidateQueries({ queryKey: ["project", id] });
      void qc.invalidateQueries({ queryKey: ["projects"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      notify(p.archived_at ? "Project archived" : "Project restored");
    },
    onError: (err) => notify(errorMessage(err), "danger"),
  });

  if (q.isLoading) return <Spinner label="Loading project" />;
  if (q.error instanceof ApiError && q.error.status === 404) {
    return <EmptyState title="Project not found" description="It may not exist, or you may not have access to it." action={<Link href="/projects" className="text-accent hover:underline">Back to projects</Link>} />;
  }
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const project = q.data;

  return (
    <>
      <PageHeader
        breadcrumb={<Link href="/projects" className="hover:underline">Projects</Link>}
        title={<span className="flex flex-wrap items-center gap-3">{project.name}<StatusBadge status={project.status} label={label(vocab?.project_statuses, project.status)} />{project.archived_at && <Badge tone="warning">Archived</Badge>}</span>}
        description={`${project.number}${project.client_company ? ` · ${project.client_company.name}` : ""}`}
        actions={
          can(P.PROJECTS_ARCHIVE) &&
          (project.archived_at ? (
            <Button variant="secondary" loading={archive.isPending} onClick={() => archive.mutate(false)}><ArchiveRestore className="size-4" />Restore</Button>
          ) : (
            <ConfirmButton
              size="md"
              label={<><Archive className="size-4" />Archive</>}
              title={`Archive ${project.number}?`}
              description="Archived projects become read-only and are hidden from lists and dashboard totals. You can restore them later."
              confirmLabel="Archive project"
              variant="primary"
              onConfirm={() => archive.mutateAsync(true)}
            />
          ))
        }
      />
      {project.archived_at && <Alert tone="warning" className="mb-4" title="This project is archived and read-only." />}
      <Tabs
        value={tab}
        onValueChange={(v) => { setTab(v); setEditing(false); }}
        tabs={[
          { value: "overview", label: "Overview" },
          { value: "team", label: "Team" },
          { value: "parties", label: "Parties" },
          { value: "phases", label: "Phases" },
          ...(can(P.ESTIMATES_VIEW) ? [{ value: "estimates", label: "Estimates" }] : []),
          ...(can(P.BUDGETS_VIEW) ? [{ value: "budget", label: "Budget" }] : []),
          { value: "documents", label: "Documents" },
          { value: "activity", label: "Activity" },
        ]}
      >
        <div className="pt-6">
          <TabPanel value="overview">
            {editing ? (
              <Card>
                <CardHeader title="Edit project" description="Changes are recorded in the audit trail with before and after values." />
                <CardBody className="py-6">
                  <ProjectForm
                    project={project}
                    onCancel={() => setEditing(false)}
                    onSaved={(p) => {
                      qc.setQueryData(["project", id], p);
                      void qc.invalidateQueries({ queryKey: ["project", id] });
                      void qc.invalidateQueries({ queryKey: ["projects"] });
                      void qc.invalidateQueries({ queryKey: ["dashboard"] });
                      setEditing(false);
                      notify("Project saved");
                    }}
                  />
                </CardBody>
              </Card>
            ) : (
              <Overview project={project} onEdit={() => setEditing(true)} />
            )}
          </TabPanel>
          <TabPanel value="team"><Team project={project} /></TabPanel>
          <TabPanel value="parties"><Parties project={project} /></TabPanel>
          <TabPanel value="phases"><Phases project={project} /></TabPanel>
          <TabPanel value="estimates"><Card><EstimatesList projectId={project.id} canCreate={!project.archived_at} /></Card></TabPanel>
          <TabPanel value="budget"><BudgetPanel project={project} /></TabPanel>
          <TabPanel value="documents"><Card><DocumentsPanel projectId={project.id} canUpload={!project.archived_at} /></Card></TabPanel>
          <TabPanel value="activity"><Activity project={project} /></TabPanel>
        </div>
      </Tabs>
    </>
  );
}
