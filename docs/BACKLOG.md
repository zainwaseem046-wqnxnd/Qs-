# Task Backlog

Priority: P0 (blocks next phase) · P1 (this phase) · P2 (soon) · P3 (later). Owner TBD until team is staffed.

## Phase 2 carry-overs (platform)
| ID | Item | Priority |
|---|---|---|
| B-1 | Transactional email provider (invitations, password reset, email verification) | P0 |
| B-2 | Password reset flow (depends on B-1) | P0 |
| B-3 | Background worker (Redis queue) with tenant-scoped job context | P0 |
| B-4 | Malware scanning of uploads (ClamAV worker or S3 Malware Protection); block download of infected files | P1 |
| B-5 | Structured JSON logging + request IDs propagated to logs | P1 |
| B-6 | Supported linter for frontend (ESLint 10 flat config or Biome) | P1 |
| B-7 | `pip-audit`, `npm audit`, Semgrep and secret scanning in CI | P1 |
| B-8 | Exercise Dockerfiles and compose stack in CI | P1 |
| B-9 | Terraform: staging VPC, RDS, ElastiCache, S3, ECS, WAF | P1 |
| B-10 | Strict CSP with nonces for the web app | P2 |
| B-11 | MFA recovery codes; admin "require MFA for this organization" | P1 |
| B-12 | Axe accessibility checks in Playwright | P2 |
| B-13 | Signed, short-lived S3 download URLs for large files | P2 |
| B-14 | Audit log export (CSV) and hash chaining | P2 |
| B-15 | Session list ("signed-in devices") with remote sign-out | P2 |

## Phase 2 product
| ID | Item | Priority |
|---|---|---|
| C-1 | Classifications + cost codes (import customer-licensed MasterFormat/UniFormat) | P0 |
| C-2 | Estimating: estimates, versions, lines, assemblies, markups, alternates, build-up view | P0 |
| C-3 | Budgets from approved estimates; transfers; revised budget | P0 |
| C-4 | Prime contracts + commitments (subcontracts/POs) | P0 |
| C-5 | Change order lifecycle with posting to contract/budget/commitments | P0 |
| C-6 | Immutable cost transaction ledger + CSV import | P0 |
| C-7 | Forecasting engine (FFC, CTC, GP, margin, WIP, over/under billing) | P0 |
| C-8 | Cost report + dashboard v2 with configurable widgets | P1 |
| C-9 | Exports: CSV, XLSX, PDF | P1 |
