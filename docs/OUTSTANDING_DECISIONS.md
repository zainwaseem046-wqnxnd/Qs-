# Outstanding Decisions

Decisions that materially affect architecture, compliance or the business and need an owner's input.

| ID | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| OD-1 | Team size and delivery timeline | — | Required before committing phase dates | Phase 2 planning |
| OD-2 | Cloud account and region (data residency) | AWS us-east-1 / us-east-2 / GovCloud | us-east-2 primary, us-west-2 DR; GovCloud only if pursuing federal work (FedRAMP) | Before staging |
| OD-3 | Email provider | Amazon SES / Postmark / SendGrid | Amazon SES (same cloud, lowest cost) | Phase 2 start |
| OD-4 | Classification licensing | Customers upload their CSI licences vs. company licenses CSI data for redistribution | Customer-provided initially; negotiate CSI licence before GA | Phase 2 (cost codes) |
| OD-5 | AIA / ConsensusDocs | Data-compatible workflows only vs. licensed form rendering partnership | Data-compatible only until a licence is in place | Phase 3 |
| OD-6 | Default AI provider terms | Zero-retention API terms, regional processing | Claude API with zero data retention; per-tenant opt-in to AI features | Phase 4 |
| OD-7 | Pricing & packaging (per-seat vs per-project vs revenue band) | — | Affects entitlement model in tenancy domain | Before GA |
| OD-8 | Whether owners/subcontractors get external portal accounts (cross-tenant collaboration) | Guest users in GC tenant vs. linked tenants | Guest access scoped to specific projects/packages | Phase 3 (bidder portal) |
| OD-9 | Mandatory MFA policy | Optional / per-tenant enforce / always | Per-tenant enforcement, default on for Owner/Admin | Phase 2 |
| OD-10 | Integration partner programmes (Procore, Autodesk, Sage, Intuit…) | — | Apply early; connectors cannot be claimed functional without approved access | Phase 6 (apply in Phase 3) |
