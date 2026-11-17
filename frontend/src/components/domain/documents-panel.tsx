"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Search, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { DataTable, Pagination, type Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBytes, formatDateTime, label, P, useVocabulary } from "@/lib/hooks";
import type { DocumentDetail, DocumentItem, Page, ProjectListItem } from "@/lib/types";

const LIMIT = 25;
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.heic,.tif,.tiff,.docx,.xlsx,.pptx,.csv,.txt,.dwg,.dxf,.ifc,.msg,.eml";

function UploadDialog({
  open,
  onOpenChange,
  projectId,
  existing,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  projectId?: string | null;
  existing?: DocumentDetail;
}) {
  const vocab = useVocabulary().data;
  const qc = useQueryClient();
  const { notify } = useToast();
  const { can } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("drawing");
  const [discipline, setDiscipline] = useState("");
  const [number, setNumber] = useState("");
  const [revision, setRevision] = useState("");
  const [notes, setNotes] = useState("");
  const [target, setTarget] = useState<string>(projectId ?? "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const projects = useQuery({
    queryKey: ["projects", "picker"],
    queryFn: () => api<Page<ProjectListItem>>("/projects", { query: { limit: 200, sort: "name", order: "asc" } }),
    enabled: open && projectId === undefined && !existing,
  });

  useEffect(() => {
    if (open) {
      setFile(null);
      setTitle("");
      setNumber("");
      setRevision("");
      setNotes("");
      setErrors({});
      setError(null);
      setTarget(projectId ?? "");
    }
  }, [open, projectId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!file) errs.file = "Choose a file";
    if (!existing && !title.trim()) errs.title = "Enter a title";
    setErrors(errs);
    if (Object.keys(errs).length || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    if (revision.trim()) fd.append("revision_label", revision.trim());
    if (!existing) {
      fd.append("title", title.trim());
      fd.append("category", category);
      if (discipline) fd.append("discipline", discipline);
      if (number.trim()) fd.append("document_number", number.trim());
      if (target) fd.append("project_id", target);
    } else if (notes.trim()) fd.append("notes", notes.trim());
    setBusy(true);
    setError(null);
    try {
      const path = existing ? `/documents/${existing.id}/versions` : "/documents";
      await api<DocumentDetail>(path, { method: "POST", body: fd });
      await qc.invalidateQueries({ queryKey: ["documents"] });
      notify(existing ? `New version of “${existing.title}” uploaded` : `“${title.trim()}” uploaded`);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={existing ? `Upload new version — ${existing.title}` : "Upload document"}
      description={existing ? `This becomes version ${existing.current_version_number + 1}. Earlier versions are kept.` : "Files are stored privately and every upload is audit-logged."}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" form="upload-form" loading={busy}><Upload className="size-4" />Upload</Button>
        </>
      }
    >
      <form id="upload-form" onSubmit={submit} noValidate className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="File" error={errors.file} hint="PDF, images, Office, CSV, DWG/DXF, IFC, email. Max 100 MB." required>
          {(p) => (
            <Input
              {...p}
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="py-1.5"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
                if (f && !title && !existing) setTitle(f.name.replace(/\.[^.]+$/, ""));
              }}
            />
          )}
        </Field>
        {!existing && (
          <>
            <Field label="Title" error={errors.title} required>
              {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} />}
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Category" required>
                {(p) => <Select {...p} value={category} onChange={(e) => setCategory(e.target.value)}><Options map={vocab?.document_categories} /></Select>}
              </Field>
              <Field label="Discipline">
                {(p) => <Select {...p} value={discipline} onChange={(e) => setDiscipline(e.target.value)}><Options map={vocab?.disciplines} placeholder="None" /></Select>}
              </Field>
              <Field label="Document / sheet number" hint="e.g. A-101">
                {(p) => <Input {...p} value={number} onChange={(e) => setNumber(e.target.value)} maxLength={80} />}
              </Field>
              {projectId === undefined && (
                <Field label="Project" hint="Leave empty for an organization-wide document">
                  {(p) => (
                    <Select {...p} value={target} onChange={(e) => setTarget(e.target.value)}>
                      <option value="">Organization-wide</option>
                      {projects.data?.items.map((pr) => <option key={pr.id} value={pr.id}>{pr.number} — {pr.name}</option>)}
                    </Select>
                  )}
                </Field>
              )}
            </div>
          </>
        )}
        <Field label="Revision label" hint="e.g. IFC, Rev 3, ASI-02">
          {(p) => <Input {...p} value={revision} onChange={(e) => setRevision(e.target.value)} maxLength={40} />}
        </Field>
        {existing && (
          <Field label="Notes">
            {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} rows={2} />}
          </Field>
        )}
        {!can(P.DOCUMENTS_UPLOAD) && <Alert tone="warning">Your role cannot upload documents.</Alert>}
      </form>
    </Dialog>
  );
}

function DocumentDialog({ documentId, onClose }: { documentId: string | null; onClose: () => void }) {
  const vocab = useVocabulary().data;
  const qc = useQueryClient();
  const { can } = useAuth();
  const { notify } = useToast();
  const [versionOpen, setVersionOpen] = useState(false);
  const q = useQuery({
    queryKey: ["documents", "detail", documentId],
    queryFn: () => api<DocumentDetail>(`/documents/${documentId}`),
    enabled: !!documentId,
  });
  const remove = useMutation({
    mutationFn: () => api(`/documents/${documentId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["documents"] });
      notify("Document deleted");
      onClose();
    },
    onError: (err) => notify(err instanceof Error ? err.message : "Delete failed", "danger"),
  });
  const doc = q.data;
  const download = async (version: number, filename: string) => {
    try {
      await downloadFile(documentId!, version, filename);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Download failed", "danger");
    }
  };

  return (
    <>
      <Dialog open={!!documentId} onOpenChange={(o) => !o && onClose()} title={doc?.title ?? "Document"} wide description={doc ? `${label(vocab?.document_categories, doc.category)}${doc.document_number ? ` · ${doc.document_number}` : ""}` : undefined}>
        {q.isLoading || !doc ? (
          <Spinner />
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {can(P.DOCUMENTS_UPLOAD) && <Button size="sm" onClick={() => setVersionOpen(true)}><Upload className="size-4" />New version</Button>}
              {can(P.DOCUMENTS_DELETE) && (
                <ConfirmButton label="Delete" title={`Delete “${doc.title}”?`} description="The document is removed from lists. Stored versions are retained for audit." confirmLabel="Delete document" onConfirm={() => remove.mutateAsync()} />
              )}
            </div>
            <h3 className="text-sm font-semibold">Version history</h3>
            <ol className="divide-y divide-border rounded-md border border-border">
              {doc.versions.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <Badge tone={v.version_number === doc.current_version_number ? "accent" : "neutral"}>v{v.version_number}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{v.original_filename}{v.revision_label && <span className="ml-2 text-xs text-subtle">{v.revision_label}</span>}</p>
                    <p className="text-xs text-subtle">
                      {formatBytes(v.size_bytes)} · {formatDateTime(v.created_at)} · SHA-256 <span className="font-mono">{v.sha256.slice(0, 12)}…</span>
                      {v.scan_status === "not_scanned" && " · not malware-scanned"}
                    </p>
                    {v.notes && <p className="mt-0.5 text-xs text-muted">{v.notes}</p>}
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => download(v.version_number, v.original_filename)} aria-label={`Download version ${v.version_number}`}>
                    <Download className="size-4" />Download
                  </Button>
                </li>
              ))}
            </ol>
          </div>
        )}
      </Dialog>
      {doc && <UploadDialog open={versionOpen} onOpenChange={setVersionOpen} existing={doc} />}
    </>
  );
}

/** projectId: string = scoped to that project; null = organization-wide only; undefined = everything visible. */
export function DocumentsPanel({ projectId, canUpload = true }: { projectId?: string | null; canUpload?: boolean }) {
  const vocab = useVocabulary().data;
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [offset, setOffset] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setQ(search); setOffset(0); }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const query = useQuery({
    queryKey: ["documents", { projectId, q, category, offset }],
    queryFn: () =>
      api<Page<DocumentItem>>("/documents", {
        query: { project_id: projectId ?? undefined, scope: projectId === null ? "organization" : "all", q, category, limit: LIMIT, offset },
      }),
    placeholderData: keepPreviousData,
  });

  const columns: Column<DocumentItem>[] = [
    {
      key: "title",
      header: "Document",
      cell: (d) => (
        <div className="flex min-w-56 items-center gap-3">
          <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
          <div className="min-w-0">
            <p className="truncate font-medium">{d.title}</p>
            <p className="truncate text-xs text-subtle">{d.current_version?.original_filename}</p>
          </div>
        </div>
      ),
    },
    { key: "number", header: "No.", cell: (d) => <span className="num">{d.document_number ?? "—"}</span> },
    { key: "category", header: "Category", cell: (d) => label(vocab?.document_categories, d.category) },
    { key: "discipline", header: "Discipline", cell: (d) => label(vocab?.disciplines, d.discipline) },
    { key: "version", header: "Version", cell: (d) => `v${d.current_version_number}${d.current_version?.revision_label ? ` · ${d.current_version.revision_label}` : ""}` },
    { key: "updated", header: "Updated", cell: (d) => <span className="num text-muted">{formatDateTime(d.updated_at)}</span> },
  ];

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, number or description" className="pl-9" aria-label="Search documents" />
        </div>
        <Select value={category} onChange={(e) => { setCategory(e.target.value); setOffset(0); }} className="w-auto" aria-label="Filter by category">
          <Options map={vocab?.document_categories} placeholder="All categories" />
        </Select>
        {canUpload && can(P.DOCUMENTS_UPLOAD) && (
          <Button onClick={() => setUploadOpen(true)}><Upload className="size-4" />Upload</Button>
        )}
      </div>
      {query.isLoading ? (
        <Spinner />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !query.data || query.data.items.length === 0 ? (
        <EmptyState icon={<FileText className="size-6" />} title={q || category ? "No documents match" : "No documents yet"} description="Upload drawings, specifications, contracts and other project records." />
      ) : (
        <>
          <DataTable caption="Documents" columns={columns} rows={query.data.items} rowKey={(d) => d.id} onRowClick={(d) => setSelected(d.id)} />
          <Pagination total={query.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} projectId={projectId} />
      <DocumentDialog documentId={selected} onClose={() => setSelected(null)} />
    </>
  );
}
