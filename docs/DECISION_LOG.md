# Decision Log (Architecture Decision Records)

Format: context → decision → consequences. Status: Accepted unless noted.

### ADR-001 Modular monolith
**Context:** 23 planned domains, small team, strong cross-domain transactions (a change order touches
contract, budget and forecast). **Decision:** one FastAPI deployable with domain packages and service
boundaries; no microservices. **Consequences:** simple deployment and transactions; boundaries are enforced
by convention and review; extraction remains possible later.

### ADR-002 PostgreSQL Row-Level Security as a second isolation layer
**Context:** a single missed `WHERE tenant_id = …` would leak data between competitors. **Decision:** every
tenant table has RLS keyed on transaction-local settings; the API connects as `qs_app` (not owner, no
BYPASSRLS); migrations run as `qs_owner`. Composite `(tenant_id, id)` FKs prevent cross-tenant references,
because FK checks bypass RLS. **Consequences:** defence in depth proven by SQL-level tests; pre-auth lookups
need narrowly scoped `SECURITY DEFINER` functions; RETURNING clauses must satisfy SELECT policies (context is
set before inserts).

### ADR-003 Transaction-local RLS context re-applied per transaction
**Context:** `set_config(..., is_local)` is safe with connection pooling but disappears on commit; reloading
attributes after commit then returned zero rows. **Decision:** the session stores its context in
`session.info` and an `after_begin` listener re-applies it to each new transaction. **Consequences:** no
context leakage across pooled connections, no manual restore calls; sessions are strictly request-scoped.

### ADR-004 Services flush, handlers commit
**Decision:** one unit of work per request; services call `flush()` only; route handlers commit once.
Failed-login audit events are committed explicitly before raising. **Consequences:** atomic multi-step
operations (e.g. project + creator membership + audit event).

### ADR-005 Synchronous SQLAlchemy with FastAPI
**Context:** async SQLAlchemy adds complexity (lazy loading pitfalls, greenlets) with little benefit for a
DB-bound CRUD API. **Decision:** sync sessions; FastAPI runs sync endpoints in a thread pool. Long-running
work goes to background workers. **Consequences:** simpler code; scale horizontally with more workers.

### ADR-006 Money representation
**Decision:** `Decimal` in Python, `NUMERIC(19,2)` for currency amounts, `NUMERIC(19,6)` unit rates,
`NUMERIC(19,4)` quantities, `NUMERIC(5,2)` percentages; ROUND_HALF_UP applied once at defined points; amounts
travel as JSON strings; floats rejected at the API boundary; inputs with more than 2 decimals rejected rather
than silently rounded; different currencies never summed. The UI never parses money into JS numbers.
**Alternative considered:** integer minor units — rejected because unit rates and quantities need more
precision than cents and NUMERIC keeps SQL aggregation exact. **Consequences:** exactness proven by tests.

### ADR-007 Cookie sessions with CSRF for the browser; Bearer for API clients
**Decision:** short-lived access JWT (15 min) + opaque rotating refresh token in HttpOnly cookies on the same
origin (Next.js proxies `/api/v1`), double-submit CSRF token; Bearer header supported for integrations.
**Consequences:** tokens are not readable by JavaScript (XSS impact reduced); refresh reuse detection gives
theft signal. JWT revocation is bounded by the 15 min TTL.

### ADR-008 Migrate entities in the phase that builds them
**Context:** the brief lists ~50 core entities. **Decision:** Phase 1 migrates only entities with services,
APIs, UI and tests; others are designed in DATABASE_SCHEMA.md and migrated with their module.
**Consequences:** no orphan tables or placeholder features; schema evolves through reviewed migrations.

### ADR-009 Classification datasets are customer-licensed
**Context:** CSI MasterFormat/UniFormat and OmniClass content is copyrighted/licensed. **Decision:** do not
ship their titles or numbering as seed data; provide import tooling and per-tenant classification systems.
Same for AIA/ConsensusDocs forms: model the data (G702/G703-compatible), not the form artwork.

### ADR-010 Next.js 15.5 (not 16) and TypeScript 5.9 (not 7)
**Context:** Next 16 and TypeScript 7 (native compiler) are recent major releases. **Decision:** use the
supported Next 15.5 line and TypeScript 5.9 for ecosystem stability; revisit at the start of Phase 3.

### ADR-011 No ESLint for now; strict TypeScript instead
**Context:** ESLint 9 is out of support and `next lint` is deprecated in Next 15.5. **Decision:** rely on
`tsc --strict` with `noUncheckedIndexedAccess` plus tests; add a supported linter (ESLint 10 flat config or
Biome) in Phase 2 (backlog item).

### ADR-012 Dependency pinning and upgrade policy
Exact pins for Python and npm (lockfile committed). Monthly dependency review; security patches within 7
days (critical) / 30 days (high); major upgrades via dedicated PRs with full test runs.

### ADR-013 Invitation links shown to the inviter (no email yet)
**Context:** no email provider is configured. **Decision:** the one-time link is shown once to the inviter
with an explicit notice; tokens are hashed at rest, single-use, 7-day expiry, bound to the invited email.
**Consequences:** email ownership is not verified in Phase 1 (risk R-6); add transactional email + email
verification in Phase 2.

### ADR-014 Project visibility through team membership
**Decision:** `projects.view_all` grants portfolio-wide visibility; otherwise users see projects whose team
includes them. Project creators are added to the team automatically. Out-of-scope records return 404.

### ADR-015 Truthful file scan status
**Decision:** with no malware scanner integrated, versions are stored as `not_scanned` and the UI states it;
uploads are still constrained by allow-lists and magic-byte checks.

### ADR-017 Two markets: United States and United Kingdom
**Context:** product owner decision (2026-11-18). **Decision:** organizations have a `country_code`
(`US` | `GB`) that sets currency (USD/GBP), measurement system (US customary/metric, changeable), time zone,
date format (MM/DD/YYYY vs DD/MM/YYYY), terminology (retainage vs retention) and address rules (state + ZIP
vs county + postcode). Addresses default to the organization's country but may be explicitly the other
country. US-only concepts (states, Davis-Bacon prevailing wage) are hidden for UK organizations.
UK-specific commercial standards (NRM, JCT/NEC, VAT, CIS) are scheduled into Phase 2+ (OD-12).

### ADR-018 Regional data residency by deployment
**Decision:** each region runs a separate stack (database, storage, secrets): US in AWS us-east-2, UK in
AWS eu-west-2 (London) for UK GDPR alignment. Organizations record `data_region` at creation (the
deployment's `QS_DEPLOYMENT_REGION`) and a deployment refuses to serve another region's organization
(`403 tenant_wrong_region`). Users sign up on their region's site. **Consequences:** no cross-region data
flows; a user working for organizations in both regions has one account per region. A global "region
picker" landing page is a later convenience.

### ADR-019 Transactional email via SMTP, sender clearviewqs@gmail.com
**Decision:** email is sent through a backend abstraction (`console` in development, `memory` in tests,
`smtp` in staging/production — enforced at startup). Initial sender: clearviewqs@gmail.com over Gmail SMTP
(STARTTLS, App Password held in the secret manager). Emails are sent after commit; failures are logged and
surfaced (e.g. `email_sent: false`) without rolling back the action. Used for invitations, password reset
and password-changed notices. **Consequences:** consumer Gmail has a ~500 recipients/day limit and weaker
deliverability; move to a custom domain (Workspace or SES with SPF/DKIM/DMARC) before onboarding customers
(OD-11). Supersedes the "link shown only to the inviter" approach of ADR-013 (the link remains as fallback).

### ADR-020 Two-factor authentication is optional
**Decision (product owner):** MFA is not mandatory and the app does not prompt users to enable it. TOTP MFA
remains available in Profile & security for users who want it. **Consequences:** account security relies on
strong passwords, rate limiting, refresh-token reuse detection and email-based recovery; per-organization
enforcement can be added later without schema changes if customers require it.

### ADR-016 Dashboard never estimates unavailable metrics
**Decision:** commercial metrics needing Phase 2 data are listed as unavailable with the reason, instead of
being approximated from contract values.
