# Testing Strategy

## Principles
* Tests run against **real PostgreSQL** with the **restricted runtime role**, so Row-Level Security is active
  in every backend test — mocks would hide isolation bugs.
* Financial logic gets dedicated, example-based tests with exact expected values (no tolerance comparisons).
* Security properties are tested as behaviour (e.g. "tenant A gets 404 for tenant B's project"), at both the
  API and SQL layers.
* A feature is "done" only when its acceptance tests pass in CI.

## Layers

| Layer | Tooling | Location | Phase 1 count |
|---|---|---|---|
| Unit — money/decimal | pytest | `backend/tests/test_money.py` | 22 |
| API integration (DB + RLS) | pytest + FastAPI TestClient | `backend/tests/test_*.py` | 142 |
| Frontend unit/component | Vitest + Testing Library (jsdom) | `frontend/src/**/*.test.ts(x)` | 23 |
| End-to-end | Playwright (Chromium; desktop + Pixel 7) | `frontend/e2e` | 11 |

### Backend suites
| Suite | Covers |
|---|---|
| `test_auth.py` | registration validation, uniform login errors, rate limiting, cookie auth + CSRF, refresh rotation & reuse detection, logout, password change revocation, MFA enrol/login/replay, MFA token misuse |
| `test_tenant_isolation.py` | cross-tenant reads/writes via API → 404; spoofed `X-Tenant-ID` → 403; **SQL-level**: no rows without context, wrong-tenant context sees nothing, cross-tenant INSERT blocked by RLS, composite FK blocks cross-tenant reference, runtime role cannot bypass RLS or alter schema |
| `test_rbac.py` | permission catalog = DB, system role definitions, invitation flows, viewer restrictions, project visibility, financial redaction, escalation prevention, last-owner protection, suspension, custom role lifecycle and privacy |
| `test_projects.py` | creation with address/client, 10 validation cases (incl. float money, >2 decimals), duplicate numbers, optimistic locking + audit diff, archive read-only, search/filter/sort/paginate, team/parties/phases |
| `test_companies.py` | CRUD, contacts, versioning, search, inactive filter |
| `test_documents.py` | upload/version/download round trip with SHA-256, disallowed/spoofed/empty/oversized files, filename sanitisation, soft delete + permission, project-scoped visibility, metadata audit |
| `test_estimating_calc.py` | golden-value build-ups (US and UK examples), 6-dp unit rounding, half-up extension, sequential/cumulative markups, alternates/exclusions, 5,000-line exact sum |
| `test_commercial_core.py` | cost code templates, CSV import (ordering, all-or-nothing, depth, duplicates), in-use protection, permissions/isolation; estimate totals, validation (floats, decimals, waste range, foreign codes), issue/lock/new version/compare, **SQL-level freeze of issued versions and approved budgets**, approval permissions, visibility; budget from estimate reconciliation, approval, one-per-project rule, dashboard totals |
| `test_contracts.py` | prime contract lifecycle (auto number, default cost code set, optimistic locking, future-date and empty execution refused, lock, close), validation (country forms, retention range, LD pairing, dates), UK forms, measured line pricing (half-up), **SQL-level freeze after execution**, void/delete drafts, permissions (PM cannot execute), visibility and tenant isolation, budget vs committed summary and dashboard |
| `test_change_orders.py` | client-side lifecycle with measured addition + omission and budget adjustment, revised contract sum (original untouched), negotiation via return-to-draft, rejection reason required, withdraw/delete, commitment changes and the revised cost summary, executed-target rule, **SQL-level freeze**, validation and negative-quantity rounding, overdue flags and dashboard, permissions/isolation/audit, UK VAR/CE labelling |
| `test_forecast_calc.py` | golden-value forecast engine: greater-of / budget / committed / manual CTC, never-negative CTC, variance, GP and margin rounding, percent complete, zero-revenue handling |
| `test_cost_management.py` | ledger posting and validation, reversal (once only, reason required, no reversing a reversal), **SQL-level append-only**, CSV import (all-or-nothing, duplicates, US/UK dates, accounting negatives, commitment links), forecast create/compute/edit/approve/freeze, one per period, permissions/isolation, dashboard uses approved only |
| `test_payments_calc.py` | golden-value G702/G703 arithmetic incl. stored materials, omissions, per-line retention, certifier cut re-claimed, half-up rounding (incl. negatives), percent-to-date conversion, line limits, billing position, UK date defaults |
| `test_payments.py` | full cycle (percent and amount claims, submit lock, one open per contract, PM cannot certify, cut needs a reason, short payment → outstanding, carry-forward to next application), **SQL-level freeze** (submitted, certified, paid), validation (floats, decimals, over-claims, dates, versions), late-approved change added before submission, return to draft / delete, permissions and isolation, UK valuation dates, dashboard outstanding and over-billing |
| `test_regions_email.py` | US/UK defaults, postcodes, region guard, country-specific contract vocabularies, invitation/reset emails |
| `test_dashboard_audit.py` | exact decimal sums grouped by currency, visibility/archive scoping, upcoming completions, audit append-only even for the schema owner, document version immutability, audit filters |

### End-to-end
* `core-workflow.spec.ts` — register → validation errors → create project → edit (audit diff visible) → add
  phase → upload drawing → version history → download → dashboard totals → navigation shows planned
  modules as non-interactive → sign out → protected route redirect → wrong password → sign in.
* Cross-tenant UI isolation (two browser contexts).
* `mobile.spec.ts` — no horizontal overflow at phone width; navigation drawer.

## Running

```bash
# backend (needs PostgreSQL with qs_test bootstrapped)
cd backend && .venv/bin/pytest -p no:warnings
# frontend unit
cd frontend && npm run typecheck && npm test
# e2e (API on :8000 with QS_REGISTER_RATE_LIMIT_PER_MINUTE=100, web on :3000)
cd frontend && npx playwright test
```

The backend test session downgrades and re-upgrades the `qs_test` database, which also verifies that the
migration is reversible.

## Gaps and next additions
* Load/performance tests (k6) — Phase 6.
* Automated accessibility scans (axe) in e2e — Phase 2.
* Security scanning (SAST, dependency audit, container scan) in CI — Phase 2.
* AI evaluation harness — Phase 4 (see AI_ARCHITECTURE.md).
* Docker images and compose stack are not yet exercised in CI.
