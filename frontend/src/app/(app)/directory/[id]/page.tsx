"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CompanyForm } from "@/components/domain/company-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, DescriptionList } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { label, P, useVocabulary } from "@/lib/hooks";
import type { Company, Contact } from "@/lib/types";

type ContactValues = Pick<Contact, "first_name" | "last_name"> & Record<"title" | "email" | "phone" | "mobile", string>;

function ContactDialog({ companyId, contact, open, onOpenChange }: { companyId: string; contact: Contact | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [v, setV] = useState<ContactValues>({ first_name: "", last_name: "", title: "", email: "", phone: "", mobile: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [lastKey, setLastKey] = useState<string | null>(null);
  const key = open ? contact?.id ?? "new" : null;
  if (key !== lastKey) {
    setLastKey(key);
    if (open) {
      setV({ first_name: contact?.first_name ?? "", last_name: contact?.last_name ?? "", title: contact?.title ?? "", email: contact?.email ?? "", phone: contact?.phone ?? "", mobile: contact?.mobile ?? "" });
      setErrors({});
      setError(null);
    }
  }
  const save = useMutation({
    mutationFn: () =>
      contact
        ? api(`/companies/${companyId}/contacts/${contact.id}`, { method: "PUT", body: v })
        : api(`/companies/${companyId}/contacts`, { method: "POST", body: v }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["company", companyId] });
      notify(contact ? "Contact updated" : "Contact added");
      onOpenChange(false);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        setError(err.message);
      }
    },
  });
  const set = (k: keyof ContactValues) => (e: React.ChangeEvent<HTMLInputElement>) => setV({ ...v, [k]: e.target.value });
  const submit = () => {
    const errs: Record<string, string> = {};
    if (!v.first_name.trim()) errs.first_name = "Required";
    if (!v.last_name.trim()) errs.last_name = "Required";
    if (v.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email)) errs.email = "Enter a valid email";
    setErrors(errs);
    if (!Object.keys(errs).length) save.mutate();
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={contact ? "Edit contact" : "Add contact"}
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={save.isPending} onClick={submit}>Save</Button></>}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="First name" error={errors.first_name} required>{(p) => <Input {...p} value={v.first_name} onChange={set("first_name")} />}</Field>
        <Field label="Last name" error={errors.last_name} required>{(p) => <Input {...p} value={v.last_name} onChange={set("last_name")} />}</Field>
        <Field label="Title" className="sm:col-span-2">{(p) => <Input {...p} value={v.title} onChange={set("title")} placeholder="Chief Estimator" />}</Field>
        <Field label="Email" error={errors.email} className="sm:col-span-2">{(p) => <Input {...p} type="email" value={v.email} onChange={set("email")} />}</Field>
        <Field label="Office phone">{(p) => <Input {...p} type="tel" value={v.phone} onChange={set("phone")} />}</Field>
        <Field label="Mobile">{(p) => <Input {...p} type="tel" value={v.mobile} onChange={set("mobile")} />}</Field>
      </div>
    </Dialog>
  );
}

export default function CompanyPage() {
  const { id } = useParams<{ id: string }>();
  const vocab = useVocabulary().data;
  const { can } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [contact, setContact] = useState<Contact | null>(null);
  const company = useQuery({ queryKey: ["company", id], queryFn: () => api<Company>(`/companies/${id}`) });
  const contacts = useQuery({ queryKey: ["company", id, "contacts"], queryFn: () => api<Contact[]>(`/companies/${id}/contacts`) });
  const removeContact = useMutation({
    mutationFn: (cid: string) => api(`/companies/${id}/contacts/${cid}`, { method: "DELETE" }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["company", id] }); notify("Contact deleted"); },
  });
  const toggleActive = useMutation({
    mutationFn: (c: Company) => api<Company>(`/companies/${id}`, { method: "PATCH", body: { version: c.version, is_active: !c.is_active } }),
    onSuccess: async (c) => { qc.setQueryData(["company", id], c); await qc.invalidateQueries({ queryKey: ["companies"] }); notify(c.is_active ? "Company reactivated" : "Company deactivated"); },
    onError: (err) => notify(err instanceof Error ? err.message : "Update failed", "danger"),
  });
  const manage = can(P.COMPANIES_MANAGE);

  if (company.isLoading) return <Spinner />;
  if (company.error instanceof ApiError && company.error.status === 404) return <EmptyState title="Company not found" action={<Link href="/directory" className="text-accent hover:underline">Back to directory</Link>} />;
  if (company.error || !company.data) return <ErrorState error={company.error} />;
  const c = company.data;
  const a = c.address;

  return (
    <>
      <PageHeader
        breadcrumb={<Link href="/directory" className="hover:underline">Directory</Link>}
        title={<span className="flex items-center gap-3">{c.name}{!c.is_active && <Badge tone="warning">Inactive</Badge>}</span>}
        description={label(vocab?.company_types, c.company_type)}
        actions={manage && (
          <>
            <Button variant="secondary" onClick={() => setEditing(true)}><Pencil className="size-4" />Edit</Button>
            <Button variant="secondary" loading={toggleActive.isPending} onClick={() => toggleActive.mutate(c)}>{c.is_active ? "Deactivate" : "Reactivate"}</Button>
          </>
        )}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Company details" />
          <CardBody>
            <DescriptionList columns={1} items={[
              { label: "Legal name", value: c.legal_name ?? "—" },
              { label: "Trades", value: c.trades.length ? c.trades.join(", ") : "—" },
              { label: "Email", value: c.email ? <a className="text-accent hover:underline" href={`mailto:${c.email}`}>{c.email}</a> : "—" },
              { label: "Phone", value: c.phone ?? "—" },
              { label: "Website", value: c.website ?? "—" },
              { label: "Address", value: a ? [a.line1, [a.city, a.state_code].filter(Boolean).join(", "), a.postal_code].filter(Boolean).join(" · ") : "—" },
            ]} />
            {c.notes && <p className="mt-4 whitespace-pre-wrap border-t border-border pt-4 text-sm text-muted">{c.notes}</p>}
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Contacts" actions={manage && <Button size="sm" onClick={() => { setContact(null); setContactOpen(true); }}><Plus className="size-4" />Add contact</Button>} />
          {contacts.isLoading ? <Spinner /> : !contacts.data?.length ? <EmptyState title="No contacts yet" /> : (
            <ul className="divide-y divide-border">
              {contacts.data.map((ct) => (
                <li key={ct.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{ct.first_name} {ct.last_name}{ct.title && <span className="ml-2 text-xs font-normal text-subtle">{ct.title}</span>}</p>
                    <p className="text-xs text-muted">{[ct.email, ct.phone, ct.mobile].filter(Boolean).join(" · ") || "No contact details"}</p>
                  </div>
                  {manage && (
                    <>
                      <Button size="sm" variant="ghost" aria-label={`Edit ${ct.first_name} ${ct.last_name}`} onClick={() => { setContact(ct); setContactOpen(true); }}><Pencil className="size-4" /></Button>
                      <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Delete ${ct.first_name} ${ct.last_name}?`} description="The contact is removed from this company." confirmLabel="Delete" onConfirm={() => removeContact.mutateAsync(ct.id)} />
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Dialog open={editing} onOpenChange={setEditing} title={`Edit ${c.name}`} wide>
        {editing && <CompanyForm company={c} onCancel={() => setEditing(false)} onSaved={async (saved) => { qc.setQueryData(["company", id], saved); await qc.invalidateQueries({ queryKey: ["companies"] }); notify("Company saved"); setEditing(false); }} />}
      </Dialog>
      <ContactDialog companyId={id} contact={contact} open={contactOpen} onOpenChange={setContactOpen} />
    </>
  );
}
