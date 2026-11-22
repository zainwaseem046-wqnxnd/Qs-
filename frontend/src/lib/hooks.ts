"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { terms } from "./region";
import type { Vocabulary } from "./types";

export function useVocabulary() {
  return useQuery({
    queryKey: ["vocabulary"],
    queryFn: () => api<Vocabulary>("/vocabulary"),
    staleTime: Infinity,
  });
}

export function label(map: Record<string, string> | undefined, key: string | null | undefined): string {
  if (!key) return "—";
  return map?.[key] ?? key.replace(/_/g, " ");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  // Dates (YYYY-MM-DD) are calendar dates: format without timezone conversion.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const t = terms();
  if (m) return t.locale === "en-GB" ? `${m[3]}/${m[2]}/${m[1]}` : `${m[2]}/${m[3]}/${m[1]}`;
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(t.locale, { month: "2-digit", day: "2-digit", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString(terms().locale, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
}

export const P = {
  TENANT_MANAGE: "tenant.manage",
  MEMBERS_VIEW: "members.view",
  MEMBERS_MANAGE: "members.manage",
  ROLES_MANAGE: "roles.manage",
  AUDIT_VIEW: "audit.view",
  DASHBOARD_VIEW: "dashboard.view",
  PROJECTS_VIEW_ALL: "projects.view_all",
  PROJECTS_CREATE: "projects.create",
  PROJECTS_EDIT: "projects.edit",
  PROJECTS_ARCHIVE: "projects.archive",
  PROJECTS_MEMBERS_MANAGE: "projects.members.manage",
  PROJECTS_FINANCIALS_VIEW: "projects.financials.view",
  COMPANIES_VIEW: "companies.view",
  COMPANIES_MANAGE: "companies.manage",
  DOCUMENTS_VIEW: "documents.view",
  DOCUMENTS_UPLOAD: "documents.upload",
  DOCUMENTS_DELETE: "documents.delete",
  COST_CODES_MANAGE: "cost_codes.manage",
  ESTIMATES_VIEW: "estimates.view",
  ESTIMATES_EDIT: "estimates.edit",
  ESTIMATES_APPROVE: "estimates.approve",
  BUDGETS_VIEW: "budgets.view",
  BUDGETS_EDIT: "budgets.edit",
  BUDGETS_APPROVE: "budgets.approve",
  CONTRACTS_VIEW: "contracts.view",
  CONTRACTS_EDIT: "contracts.edit",
  CONTRACTS_EXECUTE: "contracts.execute",
  COMMITMENTS_VIEW: "commitments.view",
  COMMITMENTS_EDIT: "commitments.edit",
  COMMITMENTS_EXECUTE: "commitments.execute",
  CHANGES_VIEW: "change_orders.view",
  CHANGES_EDIT: "change_orders.edit",
  CHANGES_APPROVE: "change_orders.approve",
  COSTS_VIEW: "costs.view",
  COSTS_EDIT: "costs.edit",
  FORECASTS_VIEW: "forecasts.view",
  FORECASTS_EDIT: "forecasts.edit",
  FORECASTS_APPROVE: "forecasts.approve",
} as const;

/** Format a non-money decimal string (quantity, rate) without float conversion: trims trailing zeros. */
export function formatDecimal(value: string | null | undefined, minPlaces = 0): string {
  if (!value) return "—";
  const [i = "0", f = ""] = value.split(".");
  let frac = f.replace(/0+$/, "");
  if (frac.length < minPlaces) frac = frac.padEnd(minPlaces, "0");
  const neg = i.startsWith("-");
  const grouped = i.replace("-", "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${neg ? "-" : ""}${grouped}${frac ? `.${frac}` : ""}`;
}
