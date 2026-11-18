# Security

QS Intelligence holds contract values, cost data, bids and legal documents — some of the most
commercially sensitive information a construction business has. Security is designed in, and every control
below is marked **Implemented** (with its test), **Planned**, or **Infrastructure** (outside application code).

> We do not claim SOC 2, ISO 27001 or any certification. The design targets **NIST CSF 2.0** alignment and
> eventual **SOC 2 Type II** readiness; certification requires an independent assessment.

## 1. Threat model (summary)

| Threat | Primary controls |
|---|---|
| Tenant A reads/writes tenant B data (bug, IDOR, injection) | App-layer tenant checks + PostgreSQL RLS + composite FKs + uniform 404/403 |
| Account takeover (stuffing, phishing, stolen tokens) | Argon2id, rate limiting, TOTP MFA, short-lived access tokens, rotating refresh tokens with reuse detection |
| CSRF / XSS against the web app | HttpOnly cookies, SameSite=Lax, double-submit CSRF token, React escaping, security headers |
| Privilege escalation inside a tenant | Server-side permission checks, can't grant permissions you don't hold, owner-only owner grants, last-owner protection |
| Malicious uploads | Extension allow-list, magic-byte verification, executable rejection, size limits, no user-controlled storage paths, `Content-Disposition: attachment`, sandbox CSP on downloads |
| Tampering with history | Append-only audit trail enforced by DB trigger + grants; immutable document versions |
| Silent overwrite of approved data | Optimistic concurrency (`version`), archived projects read-only |
| AI data leakage / prompt injection (Phase 4) | See AI_ARCHITECTURE.md: tool-mediated access under the caller's permissions, source isolation, output labelling |

## 2. Controls

### Identity & authentication — Implemented
* Passwords: Argon2id (`argon2-cffi`), 12–128 chars, NIST 800-63B style (length, no composition rules,
  trivial-value blocking). Constant-time verification with a dummy hash for unknown emails.
* Access tokens: HS256 JWT, 15 min, `typ=access`, issuer-checked. MFA challenge tokens (`typ=mfa`, 5 min)
  cannot be used as access tokens (tested).
* Refresh tokens: 256-bit random, stored as SHA-256 hashes, rotated on every use; replaying a rotated token
  outside a 30 s concurrency grace window revokes the entire session family (tested).
* Password change revokes all sessions. Logout revokes the session family.
* MFA: RFC 6238 TOTP, **optional by product decision (ADR-020)**; secrets encrypted at rest (Fernet),
  step-based replay protection, password re-confirmation to enrol or disable (tested).
* Password reset: emailed single-use links (256-bit token, SHA-256 at rest, 60-minute expiry, only the newest
  link valid), identical responses whether or not the account exists, per-email and per-IP rate limits, all
  sessions revoked on reset, "password changed" notification email (tested).
* Rate limits (Redis, in-process fallback): login per email and per IP, registration per IP, MFA and
  invitation endpoints. Edge rate limiting via WAF is **Infrastructure**.
* Login failures produce identical responses for unknown email vs wrong password (tested).
* **Planned**: SSO (OIDC/SAML via an `external_identities` table), WebAuthn/passkeys, MFA recovery codes,
  breached-password screening (k-anonymity API).

### Sessions & browser — Implemented
* Cookies: `HttpOnly`, `SameSite=Lax`, `Secure` (enforced outside development); refresh cookie scoped to
  `/api/v1/auth`.
* CSRF: double-submit token required on every non-GET cookie-authenticated request (tested).
* Headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`,
  `Cache-Control: no-store` on API responses, HSTS when secure cookies are enabled.
* **Planned**: strict nonce-based Content-Security-Policy for the web app.

### Authorisation & tenant isolation — Implemented
* Every request resolves an active membership for `X-Tenant-ID`; non-members get the same error whether or
  not the tenant exists (tested).
* RBAC: 17 permissions, 7 system roles, tenant custom roles; route-level `require(...)` dependencies.
* Project visibility: portfolio-wide only with `projects.view_all`; otherwise project-team membership.
  Invisible records return 404.
* Commercial values are redacted for roles without `projects.financials.view` — including in list views,
  dashboard totals, sort order and the audit log (tested).
* Database: RLS on every tenant table, runtime role without BYPASSRLS or DDL rights, fail-closed context,
  composite tenant FKs (tested at the SQL level, not only through the API).

### Data residency — Implemented (application) / Infrastructure (hosting)
* US and UK organizations are stored in separate regional deployments (ADR-018). Each organization records
  its `data_region`; a deployment refuses requests for another region's organization (tested).
* UK deployment targets UK GDPR / Data Protection Act 2018 obligations (privacy notice, DPA with customers,
  ICO registration, international transfer assessment for sub-processors such as model providers) — to be
  completed before UK launch.

### Email — Implemented
* SMTP over STARTTLS with certificate verification; credentials only from the secret manager; HTML bodies
  escape all user-provided values (tested); production startup fails without SMTP configured.

### Data protection
* In transit: TLS 1.2+ at the load balancer — **Infrastructure**.
* At rest: RDS/EBS encryption, S3 SSE (the S3 adapter requests `AES256`; SSE-KMS planned) — **Infrastructure**.
* Field-level encryption for MFA secrets — Implemented.
* Secrets come from environment variables / AWS Secrets Manager; the API refuses to start in staging or
  production with development secrets or insecure cookies — Implemented.
* Monetary data never passes through binary floating point — Implemented (tested).

### Files — Implemented
* Allow-listed extensions; magic-byte check for PDF/images/Office; executable signatures rejected; size limit;
  filename sanitisation; storage keys derived from IDs only; SHA-256 recorded per version.
* **Planned**: malware scanning (ClamAV worker or S3 malware protection). Until then every version is stored
  with `scan_status = not_scanned` and the UI says so — we do not claim files are scanned.

### Audit & monitoring
* Implemented: append-only `audit_events` with actor, IP, user agent, request ID and field-level diffs for
  tenants, members, roles, invitations, projects, team, parties, phases, companies, contacts, documents;
  authentication events (sign-in, failures, MFA changes, password changes, refresh-token reuse).
* Planned: structured JSON logs shipped to CloudWatch, alerting on auth anomalies, audit export, hash-chained
  audit records for tamper evidence, configurable retention.

### Software supply chain
* Exact dependency pins; lockfile for npm. CI runs lint, type checks and tests on every push.
* Planned: Dependabot/Renovate, `pip-audit` + `npm audit` gates, container image scanning, SAST (Semgrep),
  secret scanning, SBOM generation.

## 3. Operations (Planned / Infrastructure)

| Area | Plan |
|---|---|
| Backup & recovery | RDS automated backups + PITR (35 days), cross-region snapshot copy, S3 versioning; quarterly restore tests. Target RPO 15 min, RTO 4 h |
| Disaster recovery | Infrastructure as code to rebuild in a second region; documented runbook |
| Incident response | Severity matrix, on-call, customer notification within contractual/legal timelines (state breach laws vary) |
| Vulnerability management | Monthly patching, critical CVEs within 7 days, annual third-party penetration test before GA |
| Data retention | Tenant-configurable retention for documents; audit logs retained ≥ 7 years by default (construction claims/lien periods) |
| Access | SSO + MFA for staff, least privilege, no production data access without a ticketed, logged break-glass process |

## 4. NIST CSF 2.0 mapping (current state)

| Function | Phase 1 coverage |
|---|---|
| Govern (GV) | Security doc, decision log, risk register (docs/) |
| Identify (ID) | Data classification: tenant business data = confidential; asset inventory via IaC (planned) |
| Protect (PR) | PR.AA identity/MFA/RBAC; PR.DS encryption + isolation; PR.PS secure configuration checks |
| Detect (DE) | Audit trail and auth event logging; monitoring/alerting planned |
| Respond (RS) | Refresh-token family revocation; incident runbook planned |
| Recover (RC) | Backup/restore plan; to be tested in Phase 6 |

## 5. Reporting a vulnerability

Until a public security contact exists, report privately to the repository owners. Do not open public issues
for security problems.
