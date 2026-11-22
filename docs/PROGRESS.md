# Development Progress Tracker

| Phase | Milestone | Status | Evidence |
|---|---|---|---|
| 1 | Repository structure, toolchain pins | ✅ Done | `backend/pyproject.toml`, `frontend/package.json` |
| 1 | Database schema + RLS + migrations (0001) | ✅ Done | upgrade/downgrade verified each test run |
| 1 | Authentication (password, JWT, refresh rotation, CSRF, MFA) | ✅ Done | `test_auth.py` |
| 1 | Multi-tenancy + isolation | ✅ Done | `test_tenant_isolation.py`, e2e isolation test |
| 1 | Roles, permissions, invitations, members | ✅ Done | `test_rbac.py` |
| 1 | Projects (CRUD, team, parties, phases, archive) | ✅ Done | `test_projects.py`, e2e |
| 1 | Directory (companies, contacts) | ✅ Done | `test_companies.py` |
| 1 | Documents (versions, storage, validation) | ✅ Done | `test_documents.py`, e2e |
| 1 | Audit trail | ✅ Done | `test_dashboard_audit.py` |
| 1 | Design system + app shell (light/dark, responsive) | ✅ Done | component tests, e2e mobile, screenshots reviewed |
| 1 | Executive dashboard v1 | ✅ Done | `test_dashboard_audit.py`, e2e |
| 1 | CI workflow | ✅ Written | `.github/workflows/ci.yml` — not yet run on GitHub |
| 1 | Docker / compose | ⚠️ Written, unverified | no Docker daemon in build environment |
| 1 | Documentation set | ✅ Done | `docs/` |
| 1.1 | US + UK markets, regional data residency guard (migration 0002) | ✅ Done | `test_regions_email.py`, e2e UK spec |
| 1.1 | Email (SMTP) — invitations, password reset, password-changed notice | ✅ Done (console/memory tested; live Gmail send not yet tested — needs App Password) | `test_regions_email.py` |
| 1.1 | MFA optional, no prompts | ✅ Done | ADR-020 |
| 2.1 | Own-format cost codes + CSV import | ✅ Done | `test_commercial_core.py`, e2e `estimating.spec.ts` |
| 2.1 | Estimating (versions, build-up, markups, alternates, compare) | ✅ Done | `test_estimating_calc.py` (golden values), `test_commercial_core.py` |
| 2.1 | Original budget from approved estimate; approval lock | ✅ Done | `test_commercial_core.py` incl. SQL-level freeze |
| 2.1 | UK procurement routes, JCT/NEC contracts, UK roles | ✅ Done | `test_regions_email.py` |
| 2.2 | Prime contracts, subcontracts and POs; execute/close/void with DB lock | ✅ Done | `test_contracts.py`, e2e `contracts.spec.ts` |
| 2.2 | Budget vs committed by cost code; dashboard committed cost | ✅ Done | `test_contracts.py` |
| 2.3 | Change orders / variations / compensation events; derived revised sums; overdue tracking | ✅ Done | `test_change_orders.py`, e2e `change-orders.spec.ts` |
| 2 | Remaining Phase 2: cost ledger (actuals), forecasting, reporting | ⏳ Next | see BACKLOG.md |

## Latest test results (milestone 2.3)
* Backend: 137 passed (pytest, PostgreSQL 16, runtime role `qs_app` with RLS).
* Frontend: TypeScript strict — no errors; Vitest 23 passed; production build succeeded.
* E2E: 9 passed (Chromium desktop + Pixel 7 emulation), stable across consecutive runs.
