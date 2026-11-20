"""Import every ORM model so SQLAlchemy metadata and Alembic see the full schema."""

from app.domains.audit.models import AuditEvent
from app.domains.budgets.models import Budget, BudgetLine
from app.domains.companies.models import Address, Company, Contact
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.documents.models import Document, DocumentVersion
from app.domains.estimating.models import Estimate, EstimateLine, EstimateMarkup, EstimateVersion
from app.domains.identity.models import AuthSession, PasswordResetToken, User
from app.domains.projects.models import Project, ProjectMember, ProjectParty, ProjectPhase
from app.domains.tenancy.models import Invitation, Permission, Role, RolePermission, Tenant, TenantMembership

__all__ = [
    "Address",
    "AuditEvent",
    "AuthSession",
    "Budget",
    "BudgetLine",
    "Company",
    "Contact",
    "CostCode",
    "CostCodeSet",
    "Document",
    "DocumentVersion",
    "Estimate",
    "EstimateLine",
    "EstimateMarkup",
    "EstimateVersion",
    "Invitation",
    "PasswordResetToken",
    "Permission",
    "Project",
    "ProjectMember",
    "ProjectParty",
    "ProjectPhase",
    "Role",
    "RolePermission",
    "Tenant",
    "TenantMembership",
    "User",
]
