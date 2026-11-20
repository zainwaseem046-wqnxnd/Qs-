# Development Roadmap

Each phase ends only when its acceptance tests pass (see TESTING_STRATEGY.md). Dates are deliberately not
committed until team size is known (see OUTSTANDING_DECISIONS.md, OD-1).

| Phase | Theme | Status |
|---|---|---|
| 1 | Foundation | ✅ Complete (this milestone) |
| 2 | Commercial core | In progress — milestone 2.1 complete |
| 3 | Procurement & payments | Planned |
| 4 | AI intelligence | Planned |
| 5 | Advanced construction | Planned |
| 6 | Enterprise & production readiness | Planned |

## Phase 1 — Foundation ✅
Repository and toolchain · PostgreSQL schema with RLS · authentication (Argon2id, JWT + rotating refresh,
TOTP MFA, CSRF) · multi-tenancy and organisation switching · RBAC with custom roles · invitations · projects
(team, parties, phases, archive, optimistic locking) · directory · documents with immutable versions ·
append-only audit trail · design system (light/dark) · executive dashboard v1 · CI · docs.

## Phase 2 — Commercial core (next)
Milestones, each shippable:
1. **Platform hardening carry-overs:** transactional email (invitations, verification), background worker,
   malware scanning, structured logging, linter, Terraform skeleton for staging.
2. ✅ **Cost codes** in each customer's own format, CSV import (milestone 2.1).
3. ✅ **Estimating:** versions, full build-up, allowances/provisional sums, alternates, markups, comparison
   (milestone 2.1). Remaining: assemblies, historical rate comparison (needs the cost database).
4. ✅ **Original budget** from approved estimate (milestone 2.1). Remaining: budget transfers, revised budget.
5. **Contracts & commitments:** prime contracts, subcontracts/POs (commitment lines), retainage terms.
6. **Change orders:** potential → priced → submitted → approved/rejected; approvals post to contract value,
   budget and commitments.
7. **Cost ledger:** immutable `cost_transactions` (actual, committed, accrued) with reversals; CSV import from
   ERP exports.
8. **Forecasting engine:** FFC, CTC, GP, margin, variance, WIP, over/under billing — deterministic and
   documented, with no-double-counting rules between commitments, invoices, accruals and actuals.
9. **Commercial reporting & dashboard v2:** cost reports, configurable widgets, exports (CSV/XLSX/PDF).

## Phase 3 — Procurement & payments
Bid packages, invitations, bidder portal (limited external access), leveling with scope/exclusions,
award → commitment, schedule of values, owner and subcontractor pay apps (G702/G703-compatible data),
retainage records, lien-waiver tracking hooks.

## Phase 4 — AI intelligence
Ingestion + OCR, chunking and pgvector retrieval, provider abstraction (Claude default), specialist agents,
recommendation inbox with approval workflow, assistant panel with citations, evaluation harness in CI.

## Phase 5 — Advanced construction
PDF drawing viewer with scale calibration and linear/area/count/volume takeoff, revision comparison;
civil (haul tickets, equipment, fuel, unit cost); field daily reports with offline capture; compliance
(COIs, bonds, lien waivers by state, certified payroll / WH-347, Davis-Bacon); advanced forecasting; BIM (IFC).

## Phase 6 — Enterprise
Integrations framework (OAuth, external IDs, webhooks, idempotent sync, retries) with connectors only after
verified API access and licensing (Procore, ACC, Sage, Vista, CMiC, QuickBooks, P6, MS Project, Power BI,
M365, DocuSign, Stripe); SSO enforcement; advanced reporting; load testing; penetration test; DR exercise;
production launch checklist. **No production deployment without explicit authorisation.**
