import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function PageHeader({ title, description, actions, breadcrumb }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; breadcrumb?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {breadcrumb && <div className="mb-1 text-sm text-muted">{breadcrumb}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-border bg-surface p-4 shadow-card", className)}>
      <p className="text-xs font-medium uppercase tracking-wide text-subtle">{label}</p>
      <p className="num mt-2 text-2xl font-semibold text-fg">{value}</p>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}
