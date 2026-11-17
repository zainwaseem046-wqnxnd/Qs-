"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { US_STATES } from "@/lib/reference";
import type { LoginResult } from "@/lib/types";

const passwordRule = z
  .string()
  .min(12, "Use at least 12 characters")
  .max(128, "Use at most 128 characters");

const schema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name").max(200),
  email: z.email("Enter a valid email address"),
  password: passwordRule,
  organization_name: z.string().trim().min(2, "Enter your company name").max(200),
  home_state: z.string().optional(),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const { setSession } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { home_state: "" } });
  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await api<LoginResult>("/auth/register", {
        method: "POST",
        tenant: false,
        body: { ...values, home_state: values.home_state || null },
      });
      if (result.session) {
        setSession(result.session);
        router.replace("/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) form.setError(field as keyof Values, { message });
        setError(err.message);
      } else setError("Unable to create your organization. Please try again.");
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Create your organization</h2>
        <p className="mt-1 text-sm text-muted">You will be the owner and can invite your team afterwards.</p>
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      <Field label="Company name" error={errors.organization_name?.message} required>
        {(p) => <Input {...p} {...form.register("organization_name")} autoComplete="organization" autoFocus />}
      </Field>
      <Field label="Home state" hint="Used as the default for new projects" error={errors.home_state?.message}>
        {(p) => (
          <Select {...p} {...form.register("home_state")}>
            <option value="">Select a state</option>
            {Object.entries(US_STATES).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Your full name" error={errors.full_name?.message} required>
        {(p) => <Input {...p} {...form.register("full_name")} autoComplete="name" />}
      </Field>
      <Field label="Work email" error={errors.email?.message} required>
        {(p) => <Input {...p} {...form.register("email")} type="email" autoComplete="email" />}
      </Field>
      <Field label="Password" hint="At least 12 characters. A passphrase works well." error={errors.password?.message} required>
        {(p) => <Input {...p} {...form.register("password")} type="password" autoComplete="new-password" />}
      </Field>
      <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
        Create organization
      </Button>
      <p className="text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
