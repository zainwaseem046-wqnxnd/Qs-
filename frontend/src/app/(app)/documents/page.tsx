"use client";

import { DocumentsPanel } from "@/components/domain/documents-panel";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function DocumentsPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.DOCUMENTS_VIEW)) return <Alert tone="warning">Your role cannot view documents.</Alert>;
  return (
    <>
      <PageHeader title="Documents" description="Drawings, specifications, contracts, correspondence and site records across your projects. Every version is retained." />
      <Card>
        <DocumentsPanel />
      </Card>
    </>
  );
}
