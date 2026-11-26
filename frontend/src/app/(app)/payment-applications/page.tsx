"use client";

import { Suspense } from "react";
import { PaymentsPanel } from "@/components/domain/payment-applications";
import { WithProject } from "@/components/domain/project-picker";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";
import { terms } from "@/lib/region";

export default function PaymentApplicationsPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.PAYMENTS_VIEW)) return <Alert tone="warning">Your role cannot view payment applications.</Alert>;
  const t = terms();
  return (
    <>
      <PageHeader title={t.payApps} description="Billing against the prime contract: what has been applied for, certified, paid and is still outstanding." />
      <Suspense>
        <WithProject>{(project) => <PaymentsPanel project={project} />}</WithProject>
      </Suspense>
    </>
  );
}
