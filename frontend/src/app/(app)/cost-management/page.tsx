"use client";

import { Suspense } from "react";
import { CostLedger } from "@/components/domain/cost-ledger";
import { CostSummary } from "@/components/domain/cost-summary";
import { WithProject } from "@/components/domain/project-picker";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function CostManagementPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.COSTS_VIEW) && !can(P.BUDGETS_VIEW)) return <Alert tone="warning">Your role cannot view cost management.</Alert>;
  return (
    <>
      <PageHeader title="Cost Management" description="Budget, commitments, changes and actual cost by cost code, with the cost ledger." />
      <Suspense>
        <WithProject>{(project) => <div className="space-y-6"><CostSummary project={project} />{can(P.COSTS_VIEW) && <CostLedger project={project} />}</div>}</WithProject>
      </Suspense>
    </>
  );
}
