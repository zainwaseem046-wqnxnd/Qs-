"use client";

import * as Menu from "@radix-ui/react-dropdown-menu";
import { Building, ChevronsUpDown, LogOut, Menu as MenuIcon, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { region } from "@/lib/region";
import { cn } from "@/lib/cn";
import { NAV } from "./nav";
import { ThemeToggle } from "./theme";

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex h-full flex-col bg-nav text-nav-fg">
      <div className="flex h-14 items-center gap-2 px-5">
        <div className="grid size-7 place-items-center rounded-md bg-accent text-xs font-bold text-white">QS</div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-nav-strong">QS Intelligence</p>
          <p className="text-[10px] uppercase tracking-widest text-nav-fg/70">USA</p>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-3 pb-6">
        {NAV.map((group) => (
          <div key={group.section} className="mt-5">
            <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-nav-fg/60">{group.section}</p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                if (!item.href) {
                  return (
                    <li key={item.label}>
                      <span
                        aria-disabled="true"
                        title={`${item.label} is scheduled for Phase ${item.phase} of the roadmap`}
                        className="flex cursor-default items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-nav-fg/45"
                      >
                        <Icon className="size-4 shrink-0" aria-hidden />
                        <span className="flex-1 truncate">{item.label}</span>
                        <span className="rounded bg-white/5 px-1.5 py-px text-[10px] font-medium">Phase {item.phase}</span>
                      </span>
                    </li>
                  );
                }
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const text = region() === "GB" && item.ukLabel ? item.ukLabel : item.label;
                return (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
                        active ? "bg-nav-active font-medium text-nav-strong" : "hover:bg-white/5 hover:text-nav-strong",
                      )}
                    >
                      <Icon className="size-4 shrink-0" aria-hidden />
                      <span className="truncate">{text}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

function TenantSwitcher() {
  const { session, tenantId, switchTenant, tenant } = useAuth();
  const router = useRouter();
  const memberships = session?.memberships ?? [];
  const current = memberships.find((m) => m.tenant_id === tenantId);
  return (
    <Menu.Root>
      <Menu.Trigger className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-2" aria-label="Switch organization">
        <Building className="size-4 shrink-0 text-subtle" aria-hidden />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{current?.tenant_name ?? "Organization"}</span>
          <span className="block truncate text-xs text-subtle">{tenant?.role.name ?? current?.role_name ?? ""}</span>
        </span>
        {memberships.length > 1 && <ChevronsUpDown className="size-3.5 shrink-0 text-subtle" aria-hidden />}
      </Menu.Trigger>
      {memberships.length > 1 && (
        <Menu.Portal>
          <Menu.Content align="start" sideOffset={6} className="z-50 min-w-60 rounded-md border border-border bg-surface p-1 shadow-lg">
            <Menu.Label className="px-2 py-1.5 text-xs text-subtle">Organizations</Menu.Label>
            {memberships.map((m) => (
              <Menu.Item
                key={m.tenant_id}
                onSelect={() => {
                  switchTenant(m.tenant_id);
                  router.push("/dashboard");
                }}
                className="cursor-pointer rounded px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-surface-2"
              >
                <span className={cn(m.tenant_id === tenantId && "font-semibold")}>{m.tenant_name}</span>
                <span className="ml-2 text-xs text-subtle">{m.role_name}</span>
              </Menu.Item>
            ))}
          </Menu.Content>
        </Menu.Portal>
      )}
    </Menu.Root>
  );
}

function UserMenu() {
  const { session, signOut } = useAuth();
  const router = useRouter();
  const initials = (session?.user.full_name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <Menu.Root>
      <Menu.Trigger className="grid size-8 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent" aria-label="Account menu">
        {initials}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-md border border-border bg-surface p-1 shadow-lg">
          <div className="px-2 py-2">
            <p className="text-sm font-medium">{session?.user.full_name}</p>
            <p className="text-xs text-subtle">{session?.user.email}</p>
          </div>
          <Menu.Separator className="my-1 h-px bg-border" />
          <Menu.Item onSelect={() => router.push("/account")} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-surface-2">
            <UserRound className="size-4" /> Profile & security
          </Menu.Item>
          <Menu.Item
            onSelect={async () => {
              await signOut();
              router.replace("/login");
            }}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-danger outline-none data-[highlighted]:bg-surface-2"
          >
            <LogOut className="size-4" /> Sign out
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => setMobileOpen(false), [pathname]);
  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 hidden w-64 lg:block">
        <Sidebar />
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72">
            <button type="button" aria-label="Close navigation" className="absolute right-3 top-3 z-10 p-1 text-nav-fg" onClick={() => setMobileOpen(false)}>
              <X className="size-5" />
            </button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-surface/95 px-4 backdrop-blur sm:px-6">
          <button type="button" className="rounded-md p-2 text-muted hover:bg-surface-2 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
            <MenuIcon className="size-5" />
          </button>
          <TenantSwitcher />
          <div className="flex-1" />
          <ThemeToggle />
          <UserMenu />
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
