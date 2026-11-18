# Product Requirements Document — QS Intelligence USA

**Tagline:** The AI Commercial Operating System for Construction.
**Document owner:** CTO / Product. **Status:** Living document; Phase 1 requirements are final, later phases are draft.

## 1. Problem

US construction businesses run their commercial life across disconnected tools: spreadsheets for estimates
and cost reports, a project-management platform for documents and RFIs, an ERP for accounting, email for bids
and change negotiations. The commercial picture — *are we going to make money on this job, and where is the
risk?* — is reassembled by hand every month, late, and with errors. Margins in US construction are thin
(typically low single digits for GCs), so a missed change order, a double-counted commitment or an unnoticed
contractual notice deadline can erase a project's profit.

## 2. Vision

One platform where estimating, procurement, contracts, payment applications, cost control and forecasting
share one data model, and an **AI Commercial Director** continuously reviews that data — citing its sources —
to tell commercial teams where money is at risk and what to do about it. Humans approve every consequential
action.

### Differentiators
1. **Commercial-first**, not document-first: every screen is organised around cost, value and risk.
2. **Traceability**: every number links back to source records and documents; every AI statement cites
   evidence and is labelled as AI-generated.
3. **Deterministic finance**: all calculations are performed by tested application code with exact decimal
   arithmetic; AI never computes or edits financial records.
4. **US-native**: CSI classifications (customer-licensed), AIA G702/G703-compatible pay app workflows,
   retainage, lien waivers, Davis-Bacon/WH-347, state-by-state rules — versioned and sourced.

### Markets
**United States and United Kingdom** (product owner decision, 2026-11-18). Organizations choose their country
at sign-up; it drives currency (USD/GBP), units (imperial/metric), date format, terminology (retainage vs
retention) and address rules. Data is hosted in-region (US or UK). UK-specific commercial standards (NRM,
JCT/NEC, VAT, CIS) are on the Phase 2+ roadmap.

## 3. Customers and personas

| Segment | Persona | Top jobs to be done |
|---|---|---|
| General contractors / CMs | Commercial Director, Project Executive | Portfolio margin, risk, cash; approve changes and forecasts |
| | Project Manager / Project Engineer | Run the job: team, documents, subcontracts, change orders, pay apps |
| | Estimator / Preconstruction | Build and version estimates; level bids |
| | Project Accountant | Cost transactions, billing, WIP, over/under billing |
| Specialty & trade contractors | Owner / PM | Pay apps to the GC, change requests, labour productivity, lien waivers |
| Civil & infrastructure | Operations Manager | Unit-cost tracking, haul tickets, equipment, production |
| Owners & developers | Owner's Rep | Budget vs commitments, change exposure, draw approval |
| All | Field Engineer / Superintendent | Daily reports, photos, quantities — often offline |

## 4. Scope by phase

See `DEVELOPMENT_ROADMAP.md` for sequencing. Requirements for Phase 1 are detailed below; later phases are
summarised in §6.

## 5. Phase 1 requirements (Foundation) — delivered

### 5.1 Organisations and identity
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| F-1 | A company can self-register an organisation; the registrant becomes Owner | Registration creates tenant, user, owner membership and audit events; duplicate emails rejected | ✅ tested |
| F-2 | Sign-in with email/password; optional TOTP MFA | Wrong credentials give one generic error; MFA users must pass a TOTP challenge; codes cannot be replayed | ✅ tested |
| F-3 | Sessions are secure and revocable | 15-min access tokens; refresh rotation with reuse detection; logout and password change revoke sessions | ✅ tested |
| F-4 | Users can belong to several organisations and switch between them | Organisation switcher lists active memberships; data never mixes | ✅ tested (API + UI e2e) |
| F-5 | Admins invite people with a role | One-time, expiring links; existing accounts must prove their password; revocation works | ✅ tested |
| F-6 | Profile and security self-service | Change name, password; optional MFA with QR code | ✅ built; API tested |
| F-7 | US or UK organization | Country chosen at sign-up sets currency, units, time zone, date format, address rules | ✅ tested (API + e2e) |
| F-8 | Email: invitations, password reset | Invitation emailed; reset link single-use, 60 min, no account enumeration; password-changed notice | ✅ tested |

### 5.2 Roles and permissions
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| R-1 | System roles: Owner, Administrator, Executive, Commercial Manager, Project Manager, Field Engineer, Viewer | Permission sets match `permissions.py`; tested against DB | ✅ |
| R-2 | Custom roles per organisation | Create/edit/delete; cannot grant permissions the actor lacks; system roles immutable | ✅ tested |
| R-3 | Project-level visibility | Users without portfolio access see only projects whose team they are on | ✅ tested |
| R-4 | Commercial values are permissioned | Contract values hidden (API, lists, dashboard, audit diffs) without `projects.financials.view` | ✅ tested |
| R-5 | Organisation always has an owner | Last active owner cannot be demoted, suspended or removed | ✅ tested |

### 5.3 Projects
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| P-1 | Create projects with US-specific attributes | Number (unique per org), name, status, sector, type, delivery method (DBB, DB, CMAR, CM agency, IPD, JOC, P3), contract type (lump sum, GMP, cost-plus, unit price, T&M), our role, client, site address (state/ZIP validated), dates, original contract value, currency, retainage %, public works, prevailing wage, reporting period | ✅ tested |
| P-2 | Edit without silent overwrites | Optimistic concurrency; conflicting edits rejected with a clear message | ✅ tested |
| P-3 | Archive / restore | Archived projects are read-only and excluded from lists and totals | ✅ tested |
| P-4 | Team, parties and phases | Add/update/remove members with project roles; link directory companies in roles; ordered phases with date validation | ✅ tested |
| P-5 | Activity history | Every change shows who, when and before → after values | ✅ tested |
| P-6 | Search, filter, sort, paginate | By name/number, status, sector; sortable columns; archived toggle | ✅ tested |

### 5.4 Directory
| ID | Requirement | Status |
|---|---|---|
| C-1 | Companies with type, trades, contact details, address; deactivate rather than delete | ✅ tested |
| C-2 | Contacts per company | ✅ tested |

### 5.5 Documents
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| D-1 | Upload project or organisation documents with category, discipline, number, revision | Allow-listed types, content verification, size limit, SHA-256 | ✅ tested |
| D-2 | Version history | New uploads create new immutable versions; all versions downloadable | ✅ tested |
| D-3 | Permissions | Project documents follow project visibility; delete requires `documents.delete`; delete is soft | ✅ tested |
| D-4 | Search | Title, number, description; filter by category | ✅ tested |

### 5.6 Executive dashboard (Phase 1 scope)
| ID | Requirement | Status |
|---|---|---|
| X-1 | Portfolio count, status distribution, live contract value and pursuit pipeline by currency, upcoming completions, recently updated projects, recent activity | ✅ tested (exact decimal sums) |
| X-2 | Metrics that require Phase 2 data (budget, cost, commitments, forecasts, margin, cash flow) are listed as unavailable — never estimated | ✅ |
| X-3 | Role-specific views | ✅ visibility- and permission-scoped; configurable widgets are Phase 2 |

### 5.7 Non-functional
* Accessibility: WCAG 2.2 AA target — labelled controls, keyboard navigation, focus rings, skip link,
  `aria-sort`, live regions for toasts, reduced-motion support.
* Responsive: usable at 360 px wide (tested with Pixel 7 emulation).
* Performance: p95 API latency < 300 ms for list/detail endpoints at 10k projects per tenant (to be load-tested
  in Phase 6).
* Availability target at GA: 99.9 % monthly.

## 6. Later phases (summary)

* **Phase 2 — Commercial core:** cost codes (customer-licensed classifications), estimating with full line
  build-up and versions, budgets, prime contracts, commitments, change orders (full lifecycle), immutable cost
  transaction ledger, deterministic forecasting (FFC = Actual + CTC; GP = Revenue − FFC; Margin = GP / Revenue
  × 100), commercial reporting, configurable dashboard widgets, WIP and over/under billing.
* **Phase 3 — Procurement & payments:** bid packages, invitations, leveling, POs, subcontracts, schedule of
  values, G702/G703-compatible pay applications, retainage tracking.
* **Phase 4 — AI intelligence:** ingestion, retrieval with citations, specialist agents, AI Commercial Director
  assistant with human approval workflow and evaluations.
* **Phase 5 — Advanced construction:** drawing measurement, civil workflows, field productivity with offline
  capture, compliance (lien waivers, COIs, certified payroll/WH-347), advanced forecasting, BIM.
* **Phase 6 — Enterprise:** ERP and platform integrations, advanced reporting, SSO enforcement, scalability,
  penetration testing, DR exercises, production readiness.

## 7. Out of scope (explicit)

* Shipping CSI MasterFormat/UniFormat/OmniClass content, AIA or ConsensusDocs forms — only
  customer-provided/licensed material.
* Legal advice. The platform tracks contractual obligations; it does not interpret law.
* Payroll processing and general ledger replacement (we integrate with ERPs instead).

## 8. Success metrics (post-launch)
Time to produce a monthly cost report; % of change orders captured before deadline; forecast accuracy vs final
cost; weekly active commercial users per project; AI recommendation acceptance rate with citation coverage.
