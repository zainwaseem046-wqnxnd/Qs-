"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (password.length < 12) errs.password = "Use at least 12 characters";
    if (password !== confirm) errs.confirm = "Passwords do not match";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password/reset", { method: "POST", body: { token, new_password: password }, tenant: false });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reset your password");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="space-y-4">
        <Alert tone="success" title="Password updated">You have been signed out everywhere. Sign in with your new password.</Alert>
        <Link href="/login" className="block text-center text-sm font-medium text-accent hover:underline">Go to sign in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Choose a new password</h2>
        <p className="mt-1 text-sm text-muted">At least 12 characters. A passphrase works well.</p>
      </div>
      {error && (
        <Alert tone="danger">
          {error} <Link href="/forgot-password" className="font-medium text-accent underline">Request a new link</Link>
        </Alert>
      )}
      <Field label="New password" error={errors.password} required>
        {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" autoFocus />}
      </Field>
      <Field label="Confirm new password" error={errors.confirm} required>
        {(p) => <Input {...p} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />}
      </Field>
      <Button type="submit" className="w-full" loading={busy}>Update password</Button>
    </form>
  );
}
