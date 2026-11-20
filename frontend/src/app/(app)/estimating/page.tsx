"use client";

import { EstimatesList } from "@/components/domain/estimates-list";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function EstimatingPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.ESTIMATES_VIEW)) return <Alert tone="warning">Your role cannot view estimates.</Alert>;
  return (
    <>
      <PageHeader title="Estimating" description="Estimates and cost plans across your projects, with full line build-ups and version history." />
      <Card>
        <EstimatesList />
      </Card>
    </>
  );
}
