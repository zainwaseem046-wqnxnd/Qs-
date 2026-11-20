# API Specification

Base path: `/api/v1`. JSON over HTTPS. The authoritative machine-readable contract is
[`api/openapi.json`](api/openapi.json), generated from the running code (interactive docs at
`/api/v1/docs` in development). Regenerate after API changes:

```bash
cd backend && .venv/bin/python -c "import json; from app.main import create_app; json.dump(create_app().openapi(), open('../docs/api/openapi.json','w'), indent=1)"
```

## Conventions

| Topic | Convention |
|---|---|
| Authentication | Browser: `qs_access` HttpOnly cookie + `X-CSRF-Token` header (echo of `qs_csrf` cookie) on non-GET. API clients: `Authorization: Bearer <access token>` (returned by login/refresh) |
| Tenant | `X-Tenant-ID: <uuid>` on every tenant-scoped endpoint. Non-membership and unknown tenants both return `403 tenant_forbidden` |
| Money | Decimal **strings** with ≤ 2 decimals (`"12500000.00"`). JSON numbers that are floats are rejected with 422 |
| Percent | Decimal strings 0–100, ≤ 2 decimals (markups: 0–1000, ≤ 4 decimals) |
| Quantities / rates | Decimal strings; quantities ≤ 4 decimals, unit rates ≤ 6 decimals; floats rejected |
| Dates | `YYYY-MM-DD` calendar dates; timestamps ISO-8601 UTC |
| IDs | UUID strings |
| Unknown fields | Rejected (422) on request bodies |
| Pagination | `limit` (1–200, default 50) and `offset`; responses `{items,total,limit,offset}` |
| Concurrency | Mutable aggregates carry `version`; PATCH must send the current `version` or receive `409 version_conflict` |
| Errors | `{"error": {"code": "...", "message": "...", "details": ...}}`; validation details are `[{field, message}]` |
| Visibility | Records the caller may not see return `404`, identical to non-existent records |

### Error codes

| HTTP | Codes |
|---|---|
| 401 | `not_authenticated`, `token_invalid`, `invalid_credentials`, `invalid_code`, `refresh_invalid`, `refresh_superseded`, `refresh_reused`, `mfa_token_invalid` |
| 403 | `permission_denied`, `csrf_failed`, `tenant_required`, `tenant_forbidden`, `tenant_invalid`, `tenant_wrong_region` |
| 404 | `not_found`, `invitation_invalid` |
| 409 | `conflict`, `email_taken`, `duplicate_number`, `version_conflict`, `project_archived`, `version_locked`, `draft_exists`, `invalid_status`, `estimate_not_approved`, `budget_locked`, `budget_exists`, `cost_code_in_use` |
| 413 | `payload_too_large` |
| 422 | `validation_failed`, `invalid_password`, `reset_token_invalid`, `file_type_not_allowed`, `file_content_mismatch`, `file_content_rejected`, `file_empty` |
| 429 | `rate_limited` |

## Authentication flow

1. `POST /auth/login {email, password}` → either `{session, access_token}` (cookies set) or
   `{mfa_required: true, mfa_token}`.
2. If MFA: `POST /auth/mfa/verify {mfa_token, code}` → session + cookies.
3. `POST /auth/refresh` (refresh cookie) rotates tokens. Reuse of a rotated token revokes the session family.
4. `POST /auth/logout` revokes and clears cookies.

## Endpoints

| Area | Method | Path | Operation |
|---|---|---|---|
| audit | `GET` | `/api/v1/audit-events` | Audit Log |
| auth | `GET` | `/api/v1/auth/invitations/{token}` | Invitation Preview |
| auth | `GET` | `/api/v1/auth/me` | Me |
| auth | `PATCH` | `/api/v1/auth/me` | Update Profile |
| auth | `POST` | `/api/v1/auth/invitations/{token}/accept` | Invitation Accept |
| auth | `POST` | `/api/v1/auth/login` | Login |
| auth | `POST` | `/api/v1/auth/logout` | Logout |
| auth | `POST` | `/api/v1/auth/mfa/disable` | Mfa Disable |
| auth | `POST` | `/api/v1/auth/mfa/enable` | Mfa Enable |
| auth | `POST` | `/api/v1/auth/mfa/setup` | Mfa Setup |
| auth | `POST` | `/api/v1/auth/mfa/verify` | Mfa Verify |
| auth | `POST` | `/api/v1/auth/password` | Change Password |
| auth | `POST` | `/api/v1/auth/password/forgot` | Forgot Password |
| auth | `POST` | `/api/v1/auth/password/reset` | Reset Password |
| auth | `POST` | `/api/v1/auth/refresh` | Refresh |
| auth | `POST` | `/api/v1/auth/register` | Register |
| budgets | `DELETE` | `/api/v1/budgets/{budget_id}` | Delete Budget |
| budgets | `DELETE` | `/api/v1/budgets/{budget_id}/lines/{line_id}` | Delete Line |
| budgets | `GET` | `/api/v1/budgets/{budget_id}` | Get Budget |
| budgets | `GET` | `/api/v1/projects/{project_id}/budgets` | List Budgets |
| budgets | `POST` | `/api/v1/budgets/{budget_id}/approve` | Approve |
| budgets | `POST` | `/api/v1/budgets/{budget_id}/lines` | Add Line |
| budgets | `POST` | `/api/v1/projects/{project_id}/budgets` | Create Budget |
| budgets | `POST` | `/api/v1/projects/{project_id}/budgets/from-estimate` | Create From Estimate |
| budgets | `PUT` | `/api/v1/budgets/{budget_id}/lines/{line_id}` | Update Line |
| cost codes | `DELETE` | `/api/v1/cost-code-sets/{set_id}/codes/{code_id}` | Delete Code |
| cost codes | `GET` | `/api/v1/cost-code-sets` | List Sets |
| cost codes | `GET` | `/api/v1/cost-code-sets/templates` | Templates |
| cost codes | `GET` | `/api/v1/cost-code-sets/{set_id}` | Get Set |
| cost codes | `GET` | `/api/v1/cost-code-sets/{set_id}/codes` | List Codes |
| cost codes | `PATCH` | `/api/v1/cost-code-sets/{set_id}` | Update Set |
| cost codes | `PATCH` | `/api/v1/cost-code-sets/{set_id}/codes/{code_id}` | Update Code |
| cost codes | `POST` | `/api/v1/cost-code-sets` | Create Set |
| cost codes | `POST` | `/api/v1/cost-code-sets/{set_id}/codes` | Create Code |
| cost codes | `POST` | `/api/v1/cost-code-sets/{set_id}/import` | Import Codes |
| dashboard | `GET` | `/api/v1/dashboard/summary` | Summary |
| directory | `DELETE` | `/api/v1/companies/{company_id}/contacts/{contact_id}` | Delete Contact |
| directory | `GET` | `/api/v1/companies` | List Companies |
| directory | `GET` | `/api/v1/companies/{company_id}` | Get Company |
| directory | `GET` | `/api/v1/companies/{company_id}/contacts` | List Contacts |
| directory | `PATCH` | `/api/v1/companies/{company_id}` | Update Company |
| directory | `POST` | `/api/v1/companies` | Create Company |
| directory | `POST` | `/api/v1/companies/{company_id}/contacts` | Create Contact |
| directory | `PUT` | `/api/v1/companies/{company_id}/contacts/{contact_id}` | Update Contact |
| documents | `DELETE` | `/api/v1/documents/{document_id}` | Delete Document |
| documents | `GET` | `/api/v1/documents` | List Documents |
| documents | `GET` | `/api/v1/documents/{document_id}` | Get Document |
| documents | `GET` | `/api/v1/documents/{document_id}/versions/{version_number}/download` | Download Version |
| documents | `PATCH` | `/api/v1/documents/{document_id}` | Update Document |
| documents | `POST` | `/api/v1/documents` | Upload Document |
| documents | `POST` | `/api/v1/documents/{document_id}/versions` | Upload Version |
| estimating | `DELETE` | `/api/v1/estimates/{estimate_id}/versions/{number}/lines/{line_id}` | Delete Line |
| estimating | `GET` | `/api/v1/estimates` | List Estimates |
| estimating | `GET` | `/api/v1/estimates/{estimate_id}` | Get Estimate |
| estimating | `GET` | `/api/v1/estimates/{estimate_id}/compare` | Compare |
| estimating | `GET` | `/api/v1/estimates/{estimate_id}/versions/{number}` | Get Version |
| estimating | `GET` | `/api/v1/estimating/reference` | Reference |
| estimating | `PATCH` | `/api/v1/estimates/{estimate_id}` | Rename |
| estimating | `PATCH` | `/api/v1/estimates/{estimate_id}/versions/{number}` | Update Version |
| estimating | `POST` | `/api/v1/estimates/{estimate_id}/versions` | Create Version |
| estimating | `POST` | `/api/v1/estimates/{estimate_id}/versions/{number}/approve` | Approve |
| estimating | `POST` | `/api/v1/estimates/{estimate_id}/versions/{number}/issue` | Issue |
| estimating | `POST` | `/api/v1/estimates/{estimate_id}/versions/{number}/lines` | Add Line |
| estimating | `POST` | `/api/v1/estimating/calculate-line` | Calculate |
| estimating | `POST` | `/api/v1/projects/{project_id}/estimates` | Create Estimate |
| estimating | `PUT` | `/api/v1/estimates/{estimate_id}/versions/{number}/lines/{line_id}` | Update Line |
| estimating | `PUT` | `/api/v1/estimates/{estimate_id}/versions/{number}/markups` | Set Markups |
| organization | `DELETE` | `/api/v1/tenant/invitations/{invitation_id}` | Revoke Invitation |
| organization | `DELETE` | `/api/v1/tenant/members/{membership_id}` | Remove Member |
| organization | `DELETE` | `/api/v1/tenant/roles/{role_id}` | Delete Role |
| organization | `GET` | `/api/v1/tenant` | Current Tenant |
| organization | `GET` | `/api/v1/tenant/invitations` | List Invitations |
| organization | `GET` | `/api/v1/tenant/members` | List Members |
| organization | `GET` | `/api/v1/tenant/permissions` | Permission Catalog |
| organization | `GET` | `/api/v1/tenant/roles` | List Roles |
| organization | `PATCH` | `/api/v1/tenant` | Update Tenant |
| organization | `PATCH` | `/api/v1/tenant/members/{membership_id}` | Update Member |
| organization | `PATCH` | `/api/v1/tenant/roles/{role_id}` | Update Role |
| organization | `POST` | `/api/v1/tenant/invitations` | Create Invitation |
| organization | `POST` | `/api/v1/tenant/roles` | Create Role |
| projects | `DELETE` | `/api/v1/projects/{project_id}/members/{member_id}` | Remove Member |
| projects | `DELETE` | `/api/v1/projects/{project_id}/parties/{party_id}` | Remove Party |
| projects | `DELETE` | `/api/v1/projects/{project_id}/phases/{phase_id}` | Delete Phase |
| projects | `GET` | `/api/v1/projects` | List Projects |
| projects | `GET` | `/api/v1/projects/{project_id}` | Get Project |
| projects | `GET` | `/api/v1/projects/{project_id}/activity` | Project Activity |
| projects | `GET` | `/api/v1/projects/{project_id}/members` | List Members |
| projects | `GET` | `/api/v1/projects/{project_id}/parties` | List Parties |
| projects | `GET` | `/api/v1/projects/{project_id}/phases` | List Phases |
| projects | `PATCH` | `/api/v1/projects/{project_id}` | Update Project |
| projects | `PATCH` | `/api/v1/projects/{project_id}/members/{member_id}` | Update Member |
| projects | `POST` | `/api/v1/projects` | Create Project |
| projects | `POST` | `/api/v1/projects/{project_id}/archive` | Archive Project |
| projects | `POST` | `/api/v1/projects/{project_id}/members` | Add Member |
| projects | `POST` | `/api/v1/projects/{project_id}/parties` | Add Party |
| projects | `POST` | `/api/v1/projects/{project_id}/phases` | Add Phase |
| projects | `POST` | `/api/v1/projects/{project_id}/restore` | Restore Project |
| projects | `PUT` | `/api/v1/projects/{project_id}/phases/{phase_id}` | Update Phase |
| reference | `GET` | `/api/v1/vocabulary` | Vocabulary |
| system | `GET` | `/api/v1/health` | Health |

## Example: create a project

```http
POST /api/v1/projects
X-Tenant-ID: 7c0b…
Content-Type: application/json

{
  "number": "24-017",
  "name": "Riverside Medical Office Building",
  "status": "active",
  "sector": "commercial",
  "delivery_method": "cm_at_risk",
  "contract_type": "gmp",
  "original_contract_value": "12500000.00",
  "retainage_percent": "10",
  "site_address": {"city": "Austin", "state_code": "TX", "postal_code": "78701"},
  "start_date": "2026-01-12",
  "planned_completion_date": "2027-06-30",
  "is_public_works": false
}
```

`201` returns the project including `version: 1`, `can_edit`, and `financials_visible`.
