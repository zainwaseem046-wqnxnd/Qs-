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
| change orders | `DELETE` | `/api/v1/change-orders/{co_id}` | Delete |
| change orders | `DELETE` | `/api/v1/change-orders/{co_id}/lines/{line_id}` | Delete Line |
| change orders | `GET` | `/api/v1/change-orders` | List Change Orders |
| change orders | `GET` | `/api/v1/change-orders/reference` | Reference |
| change orders | `GET` | `/api/v1/change-orders/{co_id}` | Get |
| change orders | `PATCH` | `/api/v1/change-orders/{co_id}` | Update |
| change orders | `POST` | `/api/v1/change-orders` | Create |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/approve` | Change Order Approve |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/lines` | Add Line |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/reject` | Change Order Reject |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/return-to-draft` | Change Order Return To Draft |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/submit` | Change Order Submit |
| change orders | `POST` | `/api/v1/change-orders/{co_id}/withdraw` | Change Order Withdraw |
| change orders | `PUT` | `/api/v1/change-orders/{co_id}/lines/{line_id}` | Update Line |
| contracts | `DELETE` | `/api/v1/commitments/{record_id}` | Delete Commitments |
| contracts | `DELETE` | `/api/v1/commitments/{record_id}/lines/{line_id}` | Delete Line Commitments |
| contracts | `DELETE` | `/api/v1/contracts/{record_id}` | Delete Contracts |
| contracts | `DELETE` | `/api/v1/contracts/{record_id}/lines/{line_id}` | Delete Line Contracts |
| contracts | `GET` | `/api/v1/commitments` | List Commitments |
| contracts | `GET` | `/api/v1/commitments/{record_id}` | Get Commitments |
| contracts | `GET` | `/api/v1/contracts` | List Contracts |
| contracts | `GET` | `/api/v1/contracts/vocabulary` | Vocabulary |
| contracts | `GET` | `/api/v1/contracts/{record_id}` | Get Contracts |
| contracts | `GET` | `/api/v1/projects/{project_id}/commercial-summary` | Commercial Summary |
| contracts | `PATCH` | `/api/v1/commitments/{record_id}` | Update Commitments |
| contracts | `PATCH` | `/api/v1/contracts/{record_id}` | Update Contracts |
| contracts | `POST` | `/api/v1/commitments/{record_id}/close` | Close Commitments |
| contracts | `POST` | `/api/v1/commitments/{record_id}/execute` | Execute Commitments |
| contracts | `POST` | `/api/v1/commitments/{record_id}/lines` | Add Line Commitments |
| contracts | `POST` | `/api/v1/commitments/{record_id}/void` | Void Commitments |
| contracts | `POST` | `/api/v1/contracts/{record_id}/close` | Close Contracts |
| contracts | `POST` | `/api/v1/contracts/{record_id}/execute` | Execute Contracts |
| contracts | `POST` | `/api/v1/contracts/{record_id}/lines` | Add Line Contracts |
| contracts | `POST` | `/api/v1/contracts/{record_id}/void` | Void Contracts |
| contracts | `POST` | `/api/v1/projects/{project_id}/commitments` | Create Commitments |
| contracts | `POST` | `/api/v1/projects/{project_id}/contracts` | Create Contracts |
| contracts | `PUT` | `/api/v1/commitments/{record_id}/lines/{line_id}` | Update Line Commitments |
| contracts | `PUT` | `/api/v1/contracts/{record_id}/lines/{line_id}` | Update Line Contracts |
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
| cost management | `DELETE` | `/api/v1/forecasts/{forecast_id}` | Delete Forecast |
| cost management | `GET` | `/api/v1/forecasts/{forecast_id}` | Get Forecast |
| cost management | `GET` | `/api/v1/projects/{project_id}/cost-transactions` | List Transactions |
| cost management | `GET` | `/api/v1/projects/{project_id}/forecasts` | List Forecasts |
| cost management | `PATCH` | `/api/v1/forecasts/{forecast_id}` | Update Forecast |
| cost management | `POST` | `/api/v1/forecasts/{forecast_id}/approve` | Approve Forecast |
| cost management | `POST` | `/api/v1/projects/{project_id}/cost-transactions` | Post Transaction |
| cost management | `POST` | `/api/v1/projects/{project_id}/cost-transactions/import` | Import Costs |
| cost management | `POST` | `/api/v1/projects/{project_id}/cost-transactions/{tx_id}/reverse` | Reverse |
| cost management | `POST` | `/api/v1/projects/{project_id}/forecasts` | Create Forecast |
| cost management | `PUT` | `/api/v1/forecasts/{forecast_id}/lines/{line_id}` | Update Line |
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
