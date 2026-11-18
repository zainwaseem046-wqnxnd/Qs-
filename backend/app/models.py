"""Import every ORM model so SQLAlchemy metadata and Alembic see the full schema."""

from app.domains.audit.models import AuditEvent
from app.domains.companies.models import Address, Company, Contact
from app.domains.documents.models import Document, DocumentVersion
from app.domains.identity.models import AuthSession, PasswordResetToken, User
from app.domains.projects.models import Project, ProjectMember, ProjectParty, ProjectPhase
from app.domains.tenancy.models import Invitation, Permission, Role, RolePermission, Tenant, TenantMembership

__all__ = [
    "Address", "AuditEvent", "AuthSession", "Company", "Contact", "Document", "DocumentVersion",
    "Invitation", "PasswordResetToken", "Permission", "Project", "ProjectMember", "ProjectParty",
    "ProjectPhase", "Role",
    "RolePermission", "Tenant", "TenantMembership", "User",
]
