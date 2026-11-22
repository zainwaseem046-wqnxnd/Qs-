"use client";

import { Suspense } from "react";
import { ForecastPanel } from "@/components/domain/forecast-panel";
import { WithProject } from "@/components/domain/project-picker";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function ForecastingPage() {
  const { can, tenant } = useAuth();
  if (tenant && !can(P.FORECASTS_VIEW)) return <Alert tone="warning">Your role cannot view forecasts.</Alert>;
  return (
    <>
      <PageHeader title="Forecasting" description="Monthly forecasts of final cost, revenue and margin — calculated deterministically and approved as snapshots." />
      <Suspense><WithProject>{(project) => <ForecastPanel project={project} />}</WithProject></Suspense>
    </>
  );
}
