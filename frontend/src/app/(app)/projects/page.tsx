"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { FolderKanban, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Checkbox, Input, Options, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { DataTable, Pagination, type Column, type SortState } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, label, P, useVocabulary } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import type { Page, ProjectListItem } from "@/lib/types";

const LIMIT = 25;

export default function ProjectsPage() {
  const router = useRouter();
  const { can } = useAuth();
  const vocab = useVocabulary().data;
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [sector, setSector] = useState("");
  const [archived, setArchived] = useState(false);
  const [sort, setSort] = useState<SortState>({ key: "updated_at", order: "desc" });
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search);
      setOffset(0);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const query = useQuery({
    queryKey: ["projects", { q, status, sector, archived, sort, offset }],
    queryFn: () =>
      api<Page<ProjectListItem>>("/projects", {
        query: { q, status, sector, include_archived: archived, sort: sort.key, order: sort.order, limit: LIMIT, offset },
      }),
    placeholderData: keepPreviousData,
  });

  const columns: Column<ProjectListItem>[] = [
    { key: "number", header: "No.", sortable: true, cell: (p) => <span className="num font-medium">{p.number}</span> },
    {
      key: "name",
      header: "Project",
      sortable: true,
      cell: (p) => (
        <div className="min-w-48">
          <Link href={`/projects/${p.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
            {p.name}
          </Link>
          <p className="text-xs text-subtle">
            {label(vocab?.sectors, p.sector)}
            {p.client_company ? ` · ${p.client_company.name}` : ""}
          </p>
        </div>
      ),
    },
    { key: "location", header: "Location", cell: (p) => (p.city ? `${p.city}, ${p.state_code ?? ""}` : p.state_code ?? "—") },
    { key: "delivery", header: "Delivery", cell: (p) => <span className="text-muted">{label(vocab?.delivery_methods, p.delivery_method)}</span> },
    {
      key: "status",
      header: "Status",
      sortable: true,
      cell: (p) => (
        <span className="flex gap-1">
          <StatusBadge status={p.status} label={label(vocab?.project_statuses, p.status)} />
          {p.archived_at && <StatusBadge status="expired" label="Archived" />}
        </span>
      ),
    },
    { key: "start_date", header: "Start", sortable: true, cell: (p) => <span className="num">{formatDate(p.start_date)}</span> },
    ...(can(P.PROJECTS_FINANCIALS_VIEW)
      ? [{ key: "contract_value", header: "Contract value", sortable: true, align: "right" as const, cell: (p: ProjectListItem) => formatMoney(p.original_contract_value, p.currency) }]
      : []),
  ];

  const data = query.data;
  const filtered = !!(q || status || sector || archived);

  return (
    <>
      <PageHeader
        title="Projects"
        description={can(P.PROJECTS_VIEW_ALL) ? "All projects in your organization." : "Projects you are assigned to."}
        actions={
          can(P.PROJECTS_CREATE) && (
            <Link href="/projects/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-fg hover:bg-accent-hover">
              <Plus className="size-4" /> New project
            </Link>
          )
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name or number" className="pl-9" aria-label="Search projects" />
          </div>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="w-auto" aria-label="Filter by status">
            <Options map={vocab?.project_statuses} placeholder="All statuses" />
          </Select>
          <Select value={sector} onChange={(e) => { setSector(e.target.value); setOffset(0); }} className="w-auto" aria-label="Filter by sector">
            <Options map={vocab?.sectors} placeholder="All sectors" />
          </Select>
          <Checkbox label="Include archived" checked={archived} onChange={(e) => { setArchived(e.target.checked); setOffset(0); }} />
        </div>
        {query.isLoading ? (
          <Spinner />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={<FolderKanban className="size-6" />}
            title={filtered ? "No projects match your filters" : "No projects yet"}
            description={filtered ? "Try a different search or clear the filters." : "Create a project to get started."}
          />
        ) : (
          <>
            <DataTable
              caption="Projects"
              columns={columns}
              rows={data.items}
              rowKey={(p) => p.id}
              sort={sort}
              onSort={(s) => { setSort(s); setOffset(0); }}
              onRowClick={(p) => router.push(`/projects/${p.id}`)}
            />
            <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
