"use client";

import { ChangeOrdersList, changesLabel } from "@/components/domain/change-orders-list";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function ChangeOrdersPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.CHANGES_VIEW)) return <Alert tone="warning">Your role cannot view change orders.</Alert>;
  return (
    <>
      <PageHeader title={changesLabel()} description="Changes to signed contracts and subcontracts — priced, submitted, and approved or rejected, with full history." />
      <Card><ChangeOrdersList /></Card>
    </>
  );
}
