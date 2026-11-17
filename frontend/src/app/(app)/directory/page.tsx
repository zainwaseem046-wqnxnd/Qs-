"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CompanyForm } from "@/components/domain/company-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Checkbox, Input, Options, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { DataTable, Pagination, type Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { label, P, useVocabulary } from "@/lib/hooks";
import type { Company, Page } from "@/lib/types";

const LIMIT = 25;

export default function DirectoryPage() {
  const { can, tenant } = useAuth();
  const vocab = useVocabulary().data;
  const router = useRouter();
  const qc = useQueryClient();
  const { notify } = useToast();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [inactive, setInactive] = useState(false);
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search); setOffset(0); }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const query = useQuery({
    queryKey: ["companies", { q, type, inactive, offset }],
    queryFn: () => api<Page<Company>>("/companies", { query: { q, company_type: type, include_inactive: inactive, limit: LIMIT, offset } }),
    placeholderData: keepPreviousData,
    enabled: can(P.COMPANIES_VIEW),
  });

  if (tenant && !can(P.COMPANIES_VIEW)) return <Alert tone="warning">Your role cannot view the directory.</Alert>;

  const columns: Column<Company>[] = [
    {
      key: "name",
      header: "Company",
      cell: (c) => (
        <div className="min-w-48">
          <Link href={`/directory/${c.id}`} onClick={(e) => e.stopPropagation()} className="font-medium hover:underline">{c.name}</Link>
          {!c.is_active && <Badge className="ml-2">Inactive</Badge>}
          {c.legal_name && <p className="text-xs text-subtle">{c.legal_name}</p>}
        </div>
      ),
    },
    { key: "type", header: "Type", cell: (c) => label(vocab?.company_types, c.company_type) },
    { key: "trades", header: "Trades", cell: (c) => <span className="text-muted">{c.trades.join(", ") || "—"}</span> },
    { key: "location", header: "Location", cell: (c) => (c.address?.city ? `${c.address.city}, ${c.address.state_code ?? ""}` : "—") },
    { key: "contact", header: "Contact", cell: (c) => <span className="text-muted">{c.email ?? c.phone ?? "—"}</span> },
  ];

  return (
    <>
      <PageHeader
        title="Directory"
        description="Owners, design consultants, subcontractors and suppliers you work with."
        actions={can(P.COMPANIES_MANAGE) && <Button onClick={() => setOpen(true)}><Plus className="size-4" />Add company</Button>}
      />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search companies" className="pl-9" aria-label="Search companies" />
          </div>
          <Select value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }} className="w-auto" aria-label="Filter by type">
            <Options map={vocab?.company_types} placeholder="All types" />
          </Select>
          <Checkbox label="Include inactive" checked={inactive} onChange={(e) => { setInactive(e.target.checked); setOffset(0); }} />
        </div>
        {query.isLoading ? <Spinner /> : query.error ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : !query.data?.items.length ? (
          <EmptyState icon={<Building2 className="size-6" />} title={q || type ? "No companies match" : "Your directory is empty"} description="Add the owners, consultants and trade partners you work with." />
        ) : (
          <>
            <DataTable caption="Companies" columns={columns} rows={query.data.items} rowKey={(c) => c.id} onRowClick={(c) => router.push(`/directory/${c.id}`)} />
            <Pagination total={query.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      <Dialog open={open} onOpenChange={setOpen} title="Add company" wide>
        {open && (
          <CompanyForm
            onCancel={() => setOpen(false)}
            onSaved={async (c) => {
              await qc.invalidateQueries({ queryKey: ["companies"] });
              notify(`${c.name} added`);
              setOpen(false);
            }}
          />
        )}
      </Dialog>
    </>
  );
}
