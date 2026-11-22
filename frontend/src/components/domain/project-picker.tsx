"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { EmptyState, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { api } from "@/lib/api";
import type { Page, Project, ProjectListItem } from "@/lib/types";

/** Project selector kept in the URL (?project=) so views can be bookmarked and shared. */
export function WithProject({ children }: { children: (project: Project) => ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const selected = params.get("project") ?? "";
  const projects = useQuery({ queryKey: ["projects", "picker"], queryFn: () => api<Page<ProjectListItem>>("/projects", { query: { limit: 200, sort: "name", order: "asc" } }) });
  const project = useQuery({ queryKey: ["project", selected], queryFn: () => api<Project>(`/projects/${selected}`), enabled: !!selected });
  return (
    <div className="space-y-6">
      <Select className="w-full max-w-md" aria-label="Project" value={selected} onChange={(e) => router.replace(`${pathname}?project=${e.target.value}`)}>
        <option value="">Select a project…</option>
        {projects.data?.items.map((p) => <option key={p.id} value={p.id}>{p.number} — {p.name}</option>)}
      </Select>
      {!selected ? <Card><EmptyState title="Choose a project" description="Select a project to see its figures." /></Card> : project.isLoading ? <Spinner /> : project.data ? children(project.data) : null}
    </div>
  );
}
