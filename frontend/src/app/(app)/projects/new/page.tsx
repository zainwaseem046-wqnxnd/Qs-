"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProjectForm } from "@/components/domain/project-form";
import { Card, CardBody } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";

export default function NewProjectPage() {
  const router = useRouter();
  const { notify } = useToast();
  const qc = useQueryClient();
  const { can, tenant } = useAuth();
  if (tenant && !can(P.PROJECTS_CREATE)) return <Alert tone="warning">Your role cannot create projects.</Alert>;
  return (
    <>
      <PageHeader title="New project" breadcrumb={<Link href="/projects" className="hover:underline">Projects</Link>} />
      <Card>
        <CardBody className="py-6">
          {tenant && (
            <ProjectForm
              onSaved={(p) => {
                void qc.invalidateQueries({ queryKey: ["projects"] });
                void qc.invalidateQueries({ queryKey: ["dashboard"] });
                notify(`Project ${p.number} created`);
                router.push(`/projects/${p.id}`);
              }}
              onCancel={() => router.push("/projects")}
            />
          )}
        </CardBody>
      </Card>
    </>
  );
}
