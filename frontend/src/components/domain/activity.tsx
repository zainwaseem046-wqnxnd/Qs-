import { formatDateTime } from "@/lib/hooks";
import type { AuditEvent } from "@/lib/types";

function renderValue(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Audit trail list. Field-level changes are shown so every edit is traceable. */
export function ActivityList({ events, showChanges = true }: { events: AuditEvent[]; showChanges?: boolean }) {
  if (events.length === 0) return <p className="px-5 py-6 text-sm text-muted">No activity recorded yet.</p>;
  return (
    <ol className="divide-y divide-border">
      {events.map((e) => {
        const changes = e.changes && !("created" in e.changes) ? Object.entries(e.changes) : [];
        return (
          <li key={e.id} className="px-5 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="text-sm">
                <span className="font-medium">{e.actor_name ?? "System"}</span> <span className="text-muted">— {e.summary}</span>
              </p>
              <time className="text-xs text-subtle" dateTime={e.occurred_at}>
                {formatDateTime(e.occurred_at)}
              </time>
            </div>
            {showChanges && changes.length > 0 && (
              <ul className="mt-1.5 space-y-0.5 text-xs text-muted">
                {changes.slice(0, 8).map(([field, change]) => {
                  const c = change as { from?: unknown; to?: unknown };
                  const isDiff = typeof change === "object" && change !== null && "to" in c;
                  return (
                    <li key={field} className="num">
                      <span className="font-medium text-fg">{field.replace(/_/g, " ")}</span>:{" "}
                      {isDiff ? (
                        <>
                          <span className="line-through">{renderValue(c.from)}</span> → {renderValue(c.to)}
                        </>
                      ) : (
                        renderValue(change)
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
