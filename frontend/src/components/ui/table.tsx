"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right";
  className?: string;
}

export interface SortState {
  key: string;
  order: "asc" | "desc";
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  sort,
  onSort,
  onRowClick,
  caption,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sort?: SortState;
  onSort?: (sort: SortState) => void;
  onRowClick?: (row: T) => void;
  caption: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border bg-surface-2/60 text-left">
            {columns.map((col) => {
              const active = sort?.key === col.key;
              const ariaSort = active ? (sort?.order === "asc" ? "ascending" : "descending") : undefined;
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={cn("px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-subtle", col.align === "right" && "text-right", col.className)}
                >
                  {col.sortable && onSort ? (
                    <button
                      type="button"
                      className={cn("inline-flex items-center gap-1 hover:text-fg", col.align === "right" && "flex-row-reverse")}
                      onClick={() => onSort({ key: col.key, order: active && sort?.order === "asc" ? "desc" : "asc" })}
                    >
                      {col.header}
                      {active ? (
                        sort?.order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />
                      ) : (
                        <ArrowUpDown className="size-3 opacity-50" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn("border-b border-border last:border-0", onRowClick && "cursor-pointer hover:bg-surface-2/70")}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={cn("px-4 py-3 align-middle", col.align === "right" && "text-right num", col.className)}>
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex gap-2">
        <button type="button" className="rounded border border-border px-3 py-1 disabled:opacity-40" disabled={page <= 1} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </button>
        <button type="button" className="rounded border border-border px-3 py-1 disabled:opacity-40" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
          Next
        </button>
      </div>
    </nav>
  );
}
