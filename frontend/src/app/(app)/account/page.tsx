"use client";

import { ShieldCheck } from "lucide-react";
import QRCode from "qrcode";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");

function Profile() {
  const { session, reload } = useAuth();
  const { notify } = useToast();
  const [name, setName] = useState(session?.user.full_name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Card>
      <CardHeader title="Profile" />
      <CardBody>
        <form className="grid max-w-xl gap-4" onSubmit={async (e) => {
          e.preventDefault();
          if (name.trim().length < 2) return setError("Enter your full name");
          setBusy(true); setError(null);
          try { await api("/auth/me", { method: "PATCH", body: { full_name: name.trim() }, tenant: false }); await reload(); notify("Profile saved"); }
          catch (err) { setError(msg(err)); } finally { setBusy(false); }
        }}>
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Full name" required>{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Email" hint="Contact your administrator to change your sign-in email">{(p) => <Input {...p} value={session?.user.email ?? ""} disabled />}</Field>
          <div><Button type="submit" loading={busy}>Save profile</Button></div>
        </form>
      </CardBody>
    </Card>
  );
}

function PasswordCard() {
  const router = useRouter();
  const { signOut } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Card>
      <CardHeader title="Password" description="Changing your password signs you out everywhere." />
      <CardBody>
        <form className="grid max-w-xl gap-4" onSubmit={async (e) => {
          e.preventDefault(); setError(null);
          if (next.length < 12) return setError("New password must be at least 12 characters");
          if (next !== confirm) return setError("Passwords do not match");
          setBusy(true);
          try { await api("/auth/password", { method: "POST", body: { current_password: current, new_password: next }, tenant: false }); await signOut(); router.replace("/login"); }
          catch (err) { setError(msg(err)); } finally { setBusy(false); }
        }}>
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Current password" required>{(p) => <Input {...p} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />}</Field>
          <Field label="New password" hint="At least 12 characters" required>{(p) => <Input {...p} type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />}</Field>
          <Field label="Confirm new password" required>{(p) => <Input {...p} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />}</Field>
          <div><Button type="submit" loading={busy}>Change password</Button></div>
        </form>
      </CardBody>
    </Card>
  );
}

function MfaCard() {
  const { session, reload } = useAuth();
  const { notify } = useToast();
  const enabled = session?.user.mfa_enabled ?? false;
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (setup) void QRCode.toDataURL(setup.otpauth_uri, { margin: 1, width: 200 }).then(setQr);
    else setQr(null);
  }, [setup]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (err) { setError(msg(err)); } finally { setBusy(false); }
  };

  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2">Two-factor authentication {enabled ? <Badge tone="success"><ShieldCheck className="size-3" />On</Badge> : <Badge tone="warning">Off</Badge>}</span>}
        description="Use an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password, Authy) for a 6-digit code at sign-in." />
      <CardBody className="max-w-xl space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        {enabled ? (
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); void run(async () => { await api("/auth/mfa/disable", { method: "POST", body: { password, code }, tenant: false }); await reload(); setPassword(""); setCode(""); notify("Two-factor authentication disabled"); }); }}>
            <p className="text-sm text-muted">To turn off two-factor authentication, confirm your password and a current code.</p>
            <Field label="Password" required>{(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
            <Field label="Authenticator code" required>{(p) => <Input {...p} inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" />}</Field>
            <div><Button variant="danger" type="submit" loading={busy}>Disable two-factor</Button></div>
          </form>
        ) : !setup ? (
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); void run(async () => { setSetup(await api("/auth/mfa/setup", { method: "POST", body: { password }, tenant: false })); setPassword(""); }); }}>
            <Field label="Confirm your password to begin" required>{(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />}</Field>
            <div><Button type="submit" loading={busy}>Set up two-factor</Button></div>
          </form>
        ) : (
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (!/^\d{6}$/.test(code)) return setError("Enter the 6-digit code"); void run(async () => { await api("/auth/mfa/enable", { method: "POST", body: { code }, tenant: false }); await reload(); setSetup(null); setCode(""); notify("Two-factor authentication enabled"); }); }}>
            <p className="text-sm text-muted">1. Scan this QR code with your authenticator app.</p>
            {qr && <img src={qr} alt="QR code for authenticator app setup" width={200} height={200} className="rounded-md border border-border bg-white p-2" />}
            <p className="text-xs text-subtle">Can’t scan? Enter this key manually: <code className="select-all break-all font-mono text-fg">{setup.secret}</code></p>
            <Field label="2. Enter the 6-digit code shown in the app" required>{(p) => <Input {...p} inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" />}</Field>
            <div className="flex gap-2"><Button type="submit" loading={busy}>Verify and enable</Button><Button variant="secondary" onClick={() => setSetup(null)}>Cancel</Button></div>
          </form>
        )}
      </CardBody>
    </Card>
  );
}

export default function AccountPage() {
  return (
    <>
      <PageHeader title="Profile & security" />
      <div className="space-y-6">
        <Profile />
        <MfaCard />
        <PasswordCard />
      </div>
    </>
  );
}
