"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LoginResult } from "@/lib/types";

const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, "Enter the 6-digit code from your authenticator app") });

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function LoginForm() {
  const { setSession, status } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const [mfaToken, setMfaToken] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const codeForm = useForm<z.infer<typeof codeSchema>>({ resolver: zodResolver(codeSchema) });

  const finish = (result: LoginResult) => {
    if (result.session) {
      setSession(result.session);
      router.replace(next);
    }
  };

  const onLogin = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await api<LoginResult>("/auth/login", { method: "POST", body: values, tenant: false });
      if (result.mfa_required) setMfaToken(result.mfa_token);
      else finish(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to sign in. Please try again.");
    }
  });

  const onCode = codeForm.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      finish(await api<LoginResult>("/auth/mfa/verify", { method: "POST", body: { mfa_token: mfaToken, code }, tenant: false }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed");
      if (err instanceof ApiError && err.code === "mfa_token_invalid") setMfaToken(null);
    }
  });

  if (mfaToken) {
    return (
      <form onSubmit={onCode} noValidate className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Two-factor verification</h2>
          <p className="mt-1 text-sm text-muted">Enter the 6-digit code from your authenticator app.</p>
        </div>
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Verification code" error={codeForm.formState.errors.code?.message} required>
          {(p) => <Input {...p} {...codeForm.register("code")} inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus />}
        </Field>
        <Button type="submit" className="w-full" loading={codeForm.formState.isSubmitting}>
          Verify and sign in
        </Button>
        <button type="button" className="w-full text-center text-sm text-muted hover:text-fg" onClick={() => setMfaToken(null)}>
          Use a different account
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={onLogin} noValidate className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
        <p className="mt-1 text-sm text-muted">Welcome back. Sign in to your organization.</p>
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      <Field label="Work email" error={form.formState.errors.email?.message} required>
        {(p) => <Input {...p} {...form.register("email")} type="email" autoComplete="email" autoFocus />}
      </Field>
      <Field label="Password" error={form.formState.errors.password?.message} required>
        {(p) => <Input {...p} {...form.register("password")} type="password" autoComplete="current-password" />}
      </Field>
      <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
        Sign in
      </Button>
      <p className="text-center text-sm text-muted">
        New to QS Intelligence?{" "}
        <Link href="/register" className="font-medium text-accent hover:underline">
          Create an organization
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
