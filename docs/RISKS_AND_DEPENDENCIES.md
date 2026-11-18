# Risks and Dependencies

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Cross-tenant data leak | Low | Critical | RLS + app checks + composite FKs + SQL-level tests; add pentest before GA |
| R-2 | Financial calculation error erodes trust | Medium | Critical | Decimal-only arithmetic, documented formulas, golden-value tests, reconciliation reports |
| R-3 | Licensing (CSI, AIA, ConsensusDocs, integration partners) blocks features | Medium | High | Customer-provided content; early partner applications (OD-4, OD-5, OD-10) |
| R-4 | State-specific compliance rules (lien waivers, prevailing wage) are wrong or stale | Medium | High | Versioned, sourced rules with legal review; never present as legal advice |
| R-5 | AI hallucination in commercial advice | Medium | High | Cite-or-abstain, draft-only tools, human approval, evaluation gates |
| R-6 | Invitation links can be forwarded (no separate email verification step) | Low | Medium | Links are emailed to the invited address, single-use, 7-day expiry |
| R-12 | Consumer Gmail sender: daily sending limit (~500), spam filtering, account suspension | High | Medium | Custom domain with SPF/DKIM/DMARC before beta (OD-11); `email_sent` surfaced so admins can fall back to copy-link |
| R-13 | Optional MFA increases account-takeover exposure | Medium | High | Argon2id, rate limits, reuse detection, password-changed notices; offer per-organization enforcement if customers ask |
| R-14 | UK vs US legal/commercial differences (contracts, retention, tax, payment law) handled incorrectly | Medium | High | Country-scoped rules, versioned and sourced; separate UK review |
| R-7 | Uploaded malware served to other users | Low | High | Allow-list + magic bytes + attachment downloads now; scanning in Phase 2 (B-4) |
| R-8 | Docker/compose and CI not yet executed | Medium | Medium | Run CI on first push; fix before Phase 2 work (B-8) |
| R-9 | 15-minute access-token validity after revocation | Low | Medium | Short TTL; add token denylist for high-risk events if needed |
| R-10 | Scope breadth vs team capacity | High | High | Strict phase gates; build depth before breadth |
| R-11 | Next.js 15 / dependency end-of-support | Medium | Low | ADR-010/012 review at Phase 3 |

## External dependencies
PostgreSQL 16 + pgvector · Redis · S3-compatible storage · AWS (target) · email provider (Phase 2) ·
model provider API (Phase 4) · partner APIs and licences (Phase 6) · CSI data licences (customer or company).
