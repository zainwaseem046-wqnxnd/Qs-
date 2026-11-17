"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LoginResult } from "@/lib/types";

interface Preview {
  email: string;
  tenant_name: string;
  role_name: string;
  expires_at: string;
  account_exists: boolean;
}

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { setSession } = useAuth();
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(false);

  const preview = useQuery({
    queryKey: ["invite", token],
    queryFn: () => api<Preview>(`/auth/invitations/${token}`, { tenant: false }),
    retry: false,
  });

  if (preview.isLoading) return <Spinner />;
  if (preview.error || !preview.data) {
    return (
      <Alert tone="danger" title="Invitation unavailable">
        This invitation is invalid, expired or has already been used. Ask your administrator for a new link.
      </Alert>
    );
  }
  const inv = preview.data;

  if (joined) {
    return (
      <div className="space-y-4">
        <Alert tone="success" title={`You joined ${inv.tenant_name}`}>Sign in to continue.</Alert>
        <Link href="/login" className="block text-center font-medium text-accent hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!inv.account_exists && fullName.trim().length < 2) errs.full_name = "Enter your full name";
    if (!inv.account_exists && password.length < 12) errs.password = "Use at least 12 characters";
    if (inv.account_exists && !password) errs.password = "Enter your password";
    setFieldErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      const body = inv.account_exists ? { password } : { full_name: fullName.trim(), password };
      const result = await api<LoginResult>(`/auth/invitations/${token}/accept`, { method: "POST", body, tenant: false });
      if (result.session) {
        setSession(result.session);
        router.replace("/dashboard");
      } else setJoined(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors(err.fieldErrors);
        setError(err.message);
      } else setError("Unable to accept the invitation");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Join {inv.tenant_name}</h2>
        <p className="mt-1 text-sm text-muted">
          You have been invited as <strong className="text-fg">{inv.role_name}</strong> using <strong className="text-fg">{inv.email}</strong>.
        </p>
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      {inv.account_exists ? (
        <Field label="Password for your existing account" error={fieldErrors.password} required>
          {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />}
        </Field>
      ) : (
        <>
          <Field label="Full name" error={fieldErrors.full_name} required>
            {(p) => <Input {...p} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />}
          </Field>
          <Field label="Create a password" hint="At least 12 characters" error={fieldErrors.password} required>
            {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />}
          </Field>
        </>
      )}
      <Button type="submit" className="w-full" loading={busy}>
        Accept invitation
      </Button>
    </form>
  );
}
