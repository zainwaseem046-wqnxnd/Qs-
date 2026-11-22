"use client";

import { ContractsList } from "@/components/domain/contracts-list";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function ContractsPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.CONTRACTS_VIEW)) return <Alert tone="warning">Your role cannot view prime contracts.</Alert>;
  return (
    <>
      <PageHeader title="Contracts" description="Prime contracts with your clients — form, contract sum analysis, retention, dates and execution." />
      <Card><ContractsList kind="contracts" /></Card>
    </>
  );
}
