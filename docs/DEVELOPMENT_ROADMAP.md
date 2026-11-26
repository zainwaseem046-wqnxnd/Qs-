# Development Roadmap

Each phase ends only when its acceptance tests pass (see TESTING_STRATEGY.md). Dates are deliberately not
committed until team size is known (see OUTSTANDING_DECISIONS.md, OD-1).

| Phase | Theme | Status |
|---|---|---|
| 1 | Foundation | ✅ Complete (this milestone) |
| 2 | Commercial core | In progress — milestones 2.1, 2.2 and 2.3 complete |
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
5. ✅ **Contracts & commitments:** prime contracts, subcontracts/POs, retention/retainage terms, execution lock,
   budget vs committed summary (milestone 2.2). Remaining: multi-currency commitments, document links.
6. ✅ **Change orders / variations / compensation events** (milestone 2.3): priced, submitted, approved/rejected;
   revised contract sum, commitment and budget derived from approvals. Remaining: budget transfers, change events
   that fan out to several commitments, document attachments.
7. ✅ **Cost ledger** (milestone 2.4): immutable `cost_transactions` (actuals, accruals) with reversals; CSV import
   from accounting exports. Remaining: direct ERP/accounting integrations (Phase 6).
8. ✅ **Forecasting engine** (milestone 2.4): monthly FFC, CTC methods, GP, margin, variance, percent complete;
   approval freeze. Remaining: WIP and over/under billing (needs payment applications — next milestone).
9. **Commercial reporting & dashboard v2:** cost reports, configurable widgets, exports (CSV/XLSX/PDF).

## Phase 3 — Procurement & payments
✅ **Owner pay applications / UK interim valuations** (milestone 3.1): schedule of values, retention, G702/G703-
compatible figures, certification and payment, over/under billing. Remaining below: subcontractor pay apps, lien
waivers, procurement.

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
