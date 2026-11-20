# Outstanding Decisions

Decisions that materially affect architecture, compliance or the business and need an owner's input.

## Decided (2026-11-18, by the product owner)

| ID | Decision | Outcome | Recorded as |
|---|---|---|---|
| OD-2 | Markets / hosting | **United States and United Kingdom.** Separate regional deployments (US: AWS us-east-2; UK: AWS eu-west-2 London); each organization is pinned to one region | ADR-017, ADR-018 |
| OD-3 | Email | **Send from clearviewqs@gmail.com** via Gmail SMTP for now | ADR-019 |
| OD-4 | Cost-code classification | **Customers use their own formats.** Per-tenant, user-defined code structures; no CSI content shipped | ADR-009 (confirmed), Phase 2 design |
| OD-9 | Two-factor authentication | **Not mandatory.** Remains available as an option in account settings; no prompts | ADR-020 |
| OD-12 | UK standards first | **Yes:** NRM-ready cost code structures and JCT/NEC contract types from the start | ADR-023 |

## Still open

| ID | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| OD-1 | Team size and delivery timeline | — | Required before committing phase dates | Phase 2 planning |
| OD-11 | Custom sending domain before launch (e.g. notifications@yourdomain) | Google Workspace / Amazon SES with SPF, DKIM, DMARC | Move off a consumer Gmail sender before onboarding paying customers (deliverability + ~500/day limit) | Before beta |
| OD-13 | Product name for the UK market ("QS Intelligence **USA**" shows to UK customers) | Keep / "QS Intelligence" / region suffix per deployment | "QS Intelligence" as the brand, with region shown in the app | Before UK beta |
| OD-14 | Ship RICS NRM content under licence? | Customers import their own (current) / license NRM from RICS | Keep customer-provided until demand justifies a RICS licence | Before UK GA |
| OD-15 | Segregation of duties on approvals (estimator cannot approve own estimate) | Off (current) / per-organization setting | Per-organization setting in a later milestone | Phase 2 |
| OD-5 | AIA / ConsensusDocs | Data-compatible workflows only vs. licensed form rendering partnership | Data-compatible only until a licence is in place | Phase 3 |
| OD-6 | Default AI provider terms | Zero-retention API terms, regional processing | Claude API with zero data retention; per-tenant opt-in to AI features | Phase 4 |
| OD-7 | Pricing & packaging (per-seat vs per-project vs revenue band) | — | Affects entitlement model in tenancy domain | Before GA |
| OD-8 | Whether owners/subcontractors get external portal accounts (cross-tenant collaboration) | Guest users in GC tenant vs. linked tenants | Guest access scoped to specific projects/packages | Phase 3 (bidder portal) |
| OD-10 | Integration partner programmes (Procore, Autodesk, Sage, Intuit…) | — | Apply early; connectors cannot be claimed functional without approved access | Phase 6 (apply in Phase 3) |
