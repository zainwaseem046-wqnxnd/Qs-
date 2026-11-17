import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "info" | "success" | "warning" | "danger";
const alertStyles: Record<Tone, string> = {
  info: "bg-accent-soft text-fg border-accent/30",
  success: "bg-success-soft text-fg border-success/30",
  warning: "bg-warning-soft text-fg border-warning/30",
  danger: "bg-danger-soft text-fg border-danger/30",
};
const icons = { info: Info, success: CheckCircle2, warning: AlertTriangle, danger: XCircle };
const iconColor: Record<Tone, string> = { info: "text-accent", success: "text-success", warning: "text-warning", danger: "text-danger" };

export function Alert({ tone = "info", title, children, className }: { tone?: Tone; title?: string; children?: ReactNode; className?: string }) {
  const Icon = icons[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-md border px-4 py-3 text-sm", alertStyles[tone], className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", iconColor[tone])} aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && "mt-0.5", "text-muted")}>{children}</div>}
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-3 rounded-full bg-surface-2 p-3 text-subtle">{icon}</div>}
      <p className="font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong";
  return (
    <div className="p-4">
      <Alert tone="danger" title="Could not load this data">
        {message}
        {onRetry && (
          <button type="button" onClick={onRetry} className="ml-2 font-medium text-accent underline">
            Try again
          </button>
        )}
      </Alert>
    </div>
  );
}
