"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { Alert, Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth";

export default function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const { status, session } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status !== "authenticated" || !session) return <Spinner label="Checking your session" />;
  if (session.memberships.length === 0) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <Alert tone="warning" title="No active organization">
          Your account is not an active member of any organization. Ask an administrator for an invitation.
        </Alert>
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
