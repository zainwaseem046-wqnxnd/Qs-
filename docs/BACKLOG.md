# Task Backlog

Priority: P0 (blocks next phase) · P1 (this phase) · P2 (soon) · P3 (later). Owner TBD until team is staffed.

## Phase 2 carry-overs (platform)
| ID | Item | Priority |
|---|---|---|
| B-1 | ~~Transactional email (invitations, password reset)~~ — done (SMTP, ADR-019) | ✅ |
| B-2 | ~~Password reset flow~~ — done | ✅ |
| B-1a | Custom sending domain with SPF/DKIM/DMARC (OD-11) | P1 |
| B-16 | Regional deployment configs (US us-east-2, UK eu-west-2) in Terraform | P1 |
| B-17 | Region picker landing page (us./uk. sites) | P2 |
| B-3 | Background worker (Redis queue) with tenant-scoped job context | P0 |
| B-4 | Malware scanning of uploads (ClamAV worker or S3 Malware Protection); block download of infected files | P1 |
| B-5 | Structured JSON logging + request IDs propagated to logs | P1 |
| B-6 | Supported linter for frontend (ESLint 10 flat config or Biome) | P1 |
| B-7 | `pip-audit`, `npm audit`, Semgrep and secret scanning in CI | P1 |
| B-8 | Exercise Dockerfiles and compose stack in CI | P1 |
| B-9 | Terraform: staging VPC, RDS, ElastiCache, S3, ECS, WAF | P1 |
| B-10 | Strict CSP with nonces for the web app | P2 |
| B-11 | MFA recovery codes (MFA stays optional — ADR-020) | P3 |
| B-12 | Axe accessibility checks in Playwright | P2 |
| B-13 | Signed, short-lived S3 download URLs for large files | P2 |
| B-14 | Audit log export (CSV) and hash chaining | P2 |
| B-15 | Session list ("signed-in devices") with remote sign-out | P2 |

## Phase 2 product
| ID | Item | Priority |
|---|---|---|
| C-1 | ~~Cost codes in each customer's own format~~ — done (2.1) | ✅ |
| C-2a | Estimating: assemblies (reusable priced build-ups) | P1 |
| C-2b | Estimate import/export (CSV/XLSX) and printable cost plan report | P1 |
| C-2c | Line reordering and bulk edit | P2 |
| C-3a | Budget transfers and revised budget | P0 |
| C-4 | ~~Prime contracts and commitments~~ — done (2.2) | ✅ |
| C-5 | ~~Change orders / variations / compensation events~~ — done (2.3) | ✅ |
| C-5a | Change events: one potential change fanning out to client CO + several subcontract COs | P1 |
| C-5b | Attach instructions/quotes (Documents) to change orders | P1 |
| C-5c | NEC programme of time-bar reminders (notifications) | P2 |
| C-4a | Link executed contracts to signed documents (Documents module) | P1 |
| C-4b | Multi-currency commitments with locked exchange rates | P2 |
| C-4c | Contract obligations/notice register (feeds Phase 4 contract agent) | P1 |
| C-10 | ~~UK delivery routes, JCT/NEC contract types~~ — done (2.1); remaining: VAT and CIS handling | P1 |
| C-2 | ~~Estimating core~~ — done (2.1) | ✅ |
| C-3 | ~~Original budget from approved estimate~~ — done (2.1) | ✅ |
| C-6 | Immutable cost transaction ledger + CSV import | P0 |
| C-7 | Forecasting engine (FFC, CTC, GP, margin, WIP, over/under billing) | P0 |
| C-8 | Cost report + dashboard v2 with configurable widgets | P1 |
| C-9 | Exports: CSV, XLSX, PDF | P1 |
