"use client";

import * as T from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export function Tabs({ value, onValueChange, tabs, children }: { value: string; onValueChange: (v: string) => void; tabs: { value: string; label: string; count?: number }[]; children: ReactNode }) {
  return (
    <T.Root value={value} onValueChange={onValueChange}>
      <T.List className="flex gap-1 overflow-x-auto border-b border-border" aria-label="Sections">
        {tabs.map((t) => (
          <T.Trigger
            key={t.value}
            value={t.value}
            className="-mb-px whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-sm font-medium text-muted hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg"
          >
            {t.label}
            {t.count !== undefined && <span className="ml-1.5 rounded-full bg-surface-2 px-1.5 text-xs text-subtle">{t.count}</span>}
          </T.Trigger>
        ))}
      </T.List>
      {children}
    </T.Root>
  );
}

export const TabPanel = T.Content;
