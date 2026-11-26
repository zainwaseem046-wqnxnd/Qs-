"""Import every ORM model so SQLAlchemy metadata and Alembic see the full schema."""

from app.domains.audit.models import AuditEvent
from app.domains.budgets.models import Budget, BudgetLine
from app.domains.change_orders.models import ChangeOrder, ChangeOrderLine
from app.domains.companies.models import Address, Company, Contact
from app.domains.contracts.models import Commitment, CommitmentLine, Contract, ContractLine
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.cost_management.models import CostImportBatch, CostTransaction, Forecast, ForecastLine
from app.domains.documents.models import Document, DocumentVersion
from app.domains.estimating.models import Estimate, EstimateLine, EstimateMarkup, EstimateVersion
from app.domains.identity.models import AuthSession, PasswordResetToken, User
from app.domains.payments.models import PaymentApplication, PaymentApplicationLine
from app.domains.projects.models import Project, ProjectMember, ProjectParty, ProjectPhase
from app.domains.tenancy.models import Invitation, Permission, Role, RolePermission, Tenant, TenantMembership

__all__ = [
    "Address",
    "AuditEvent",
    "AuthSession",
    "Budget",
    "BudgetLine",
    "ChangeOrder",
    "ChangeOrderLine",
    "Commitment",
    "CommitmentLine",
    "Company",
    "Contact",
    "Contract",
    "ContractLine",
    "CostCode",
    "CostCodeSet",
    "CostImportBatch",
    "CostTransaction",
    "Document",
    "DocumentVersion",
    "Estimate",
    "EstimateLine",
    "EstimateMarkup",
    "EstimateVersion",
    "Forecast",
    "ForecastLine",
    "Invitation",
    "PasswordResetToken",
    "PaymentApplication",
    "PaymentApplicationLine",
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
