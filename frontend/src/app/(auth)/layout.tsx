import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/shell/theme";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,32rem)]">
      <section className="relative hidden overflow-hidden bg-nav p-12 text-nav-fg lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-2">
          <div className="grid size-8 place-items-center rounded-md bg-accent text-sm font-bold text-white">QS</div>
          <span className="font-semibold text-nav-strong">QS Intelligence USA</span>
        </div>
        <div className="max-w-lg">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight text-nav-strong">
            The AI Commercial Operating System for Construction.
          </h1>
          <p className="mt-4 text-base leading-relaxed">
            Estimating, procurement, contracts, payment applications, cost control and forecasting in one platform —
            with every number traceable to its source.
          </p>
        </div>
        <p className="text-xs text-nav-fg/60">Tenant-isolated · Audit-logged · Built for U.S. contractors, owners and specialty trades</p>
      </section>
      <section className="flex flex-col">
        <div className="flex justify-end p-4">
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </section>
    </div>
  );
}
