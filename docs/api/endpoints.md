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
