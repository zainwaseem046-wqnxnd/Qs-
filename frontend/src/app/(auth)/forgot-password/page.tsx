"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) return setFieldError("Enter a valid email address");
    setFieldError(undefined);
    setBusy(true);
    try {
      await api("/auth/password/forgot", { method: "POST", body: { email: email.trim() }, tenant: false });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className="space-y-4">
        <Alert tone="success" title="Check your email">
          If an account exists for {email.trim()}, we sent a link to reset your password. It expires in 60 minutes.
        </Alert>
        <Link href="/login" className="block text-center text-sm font-medium text-accent hover:underline">Back to sign in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Reset your password</h2>
        <p className="mt-1 text-sm text-muted">Enter your work email and we’ll send you a reset link.</p>
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      <Field label="Work email" error={fieldError} required>
        {(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus />}
      </Field>
      <Button type="submit" className="w-full" loading={busy}>Send reset link</Button>
      <Link href="/login" className="block text-center text-sm text-muted hover:text-fg">Back to sign in</Link>
    </form>
  );
}
