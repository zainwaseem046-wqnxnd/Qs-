"use client";

import { ContractsList } from "@/components/domain/contracts-list";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function SubcontractsPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.COMMITMENTS_VIEW)) return <Alert tone="warning">Your role cannot view subcontracts and purchase orders.</Alert>;
  return (
    <>
      <PageHeader title="Subcontracts & Purchase Orders" description="Committed cost with subcontractors and suppliers, coded against your budget." />
      <Card><ContractsList kind="commitments" /></Card>
    </>
  );
}
