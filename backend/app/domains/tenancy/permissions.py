"""Permission catalog and system role definitions.

This module is the single source of truth. Migrations seed the database from it, and a test asserts
that the database catalog matches it exactly (so a new permission cannot ship without a migration).
"""

from __future__ import annotations

from enum import StrEnum


class P(StrEnum):
    TENANT_MANAGE = "tenant.manage"
    MEMBERS_VIEW = "members.view"
    MEMBERS_MANAGE = "members.manage"
    ROLES_MANAGE = "roles.manage"
    AUDIT_VIEW = "audit.view"
    DASHBOARD_VIEW = "dashboard.view"
    PROJECTS_VIEW_ALL = "projects.view_all"
    PROJECTS_CREATE = "projects.create"
    PROJECTS_EDIT = "projects.edit"
    PROJECTS_ARCHIVE = "projects.archive"
    PROJECTS_MEMBERS_MANAGE = "projects.members.manage"
    PROJECTS_FINANCIALS_VIEW = "projects.financials.view"
    COMPANIES_VIEW = "companies.view"
    COMPANIES_MANAGE = "companies.manage"
    DOCUMENTS_VIEW = "documents.view"
    DOCUMENTS_UPLOAD = "documents.upload"
    DOCUMENTS_DELETE = "documents.delete"
    COST_CODES_MANAGE = "cost_codes.manage"
    ESTIMATES_VIEW = "estimates.view"
    ESTIMATES_EDIT = "estimates.edit"
    ESTIMATES_APPROVE = "estimates.approve"
    BUDGETS_VIEW = "budgets.view"
    BUDGETS_EDIT = "budgets.edit"
    BUDGETS_APPROVE = "budgets.approve"
    CONTRACTS_VIEW = "contracts.view"
    CONTRACTS_EDIT = "contracts.edit"
    CONTRACTS_EXECUTE = "contracts.execute"
    COMMITMENTS_VIEW = "commitments.view"
    COMMITMENTS_EDIT = "commitments.edit"
    COMMITMENTS_EXECUTE = "commitments.execute"
    CHANGES_VIEW = "change_orders.view"
    CHANGES_EDIT = "change_orders.edit"
    CHANGES_APPROVE = "change_orders.approve"
    COSTS_VIEW = "costs.view"
    COSTS_EDIT = "costs.edit"
    FORECASTS_VIEW = "forecasts.view"
    FORECASTS_EDIT = "forecasts.edit"
    FORECASTS_APPROVE = "forecasts.approve"


PERMISSION_CATALOG: dict[str, tuple[str, str]] = {
    P.TENANT_MANAGE: ("Organization", "Manage organization settings"),
    P.MEMBERS_VIEW: ("Organization", "View organization members"),
    P.MEMBERS_MANAGE: ("Organization", "Invite, suspend and change roles of members"),
    P.ROLES_MANAGE: ("Organization", "Create and edit custom roles"),
    P.AUDIT_VIEW: ("Organization", "View the organization audit log"),
    P.DASHBOARD_VIEW: ("Dashboard", "View the executive dashboard"),
    P.PROJECTS_VIEW_ALL: ("Projects", "View all projects (not only assigned projects)"),
    P.PROJECTS_CREATE: ("Projects", "Create projects"),
    P.PROJECTS_EDIT: ("Projects", "Edit project details, parties and phases"),
    P.PROJECTS_ARCHIVE: ("Projects", "Archive and restore projects"),
    P.PROJECTS_MEMBERS_MANAGE: ("Projects", "Manage project team membership"),
    P.PROJECTS_FINANCIALS_VIEW: ("Projects", "View contract values and commercial figures"),
    P.COMPANIES_VIEW: ("Directory", "View companies and contacts"),
    P.COMPANIES_MANAGE: ("Directory", "Create and edit companies and contacts"),
    P.DOCUMENTS_VIEW: ("Documents", "View and download documents"),
    P.DOCUMENTS_UPLOAD: ("Documents", "Upload documents and new versions"),
    P.DOCUMENTS_DELETE: ("Documents", "Delete documents"),
    P.COST_CODES_MANAGE: ("Commercial", "Create and import cost code structures"),
    P.ESTIMATES_VIEW: ("Commercial", "View estimates"),
    P.ESTIMATES_EDIT: ("Commercial", "Create and edit draft estimates"),
    P.ESTIMATES_APPROVE: ("Commercial", "Approve issued estimates"),
    P.BUDGETS_VIEW: ("Commercial", "View project budgets"),
    P.BUDGETS_EDIT: ("Commercial", "Create and edit draft budgets"),
    P.BUDGETS_APPROVE: ("Commercial", "Approve original budgets"),
    P.CONTRACTS_VIEW: ("Contracts", "View prime contracts with clients"),
    P.CONTRACTS_EDIT: ("Contracts", "Create and edit draft prime contracts"),
    P.CONTRACTS_EXECUTE: ("Contracts", "Execute, close and void prime contracts"),
    P.COMMITMENTS_VIEW: ("Contracts", "View subcontracts and purchase orders"),
    P.COMMITMENTS_EDIT: ("Contracts", "Create and edit draft subcontracts and purchase orders"),
    P.COMMITMENTS_EXECUTE: ("Contracts", "Execute, close and void subcontracts and purchase orders"),
    P.CHANGES_VIEW: ("Change orders", "View change orders / variations"),
    P.CHANGES_EDIT: ("Change orders", "Create, price and submit change orders / variations"),
    P.CHANGES_APPROVE: ("Change orders", "Approve or reject change orders / variations"),
    P.COSTS_VIEW: ("Cost management", "View actual cost and accruals"),
    P.COSTS_EDIT: ("Cost management", "Post, import and reverse cost transactions"),
    P.FORECASTS_VIEW: ("Cost management", "View forecasts"),
    P.FORECASTS_EDIT: ("Cost management", "Prepare draft forecasts"),
    P.FORECASTS_APPROVE: ("Cost management", "Approve forecasts"),
}

ALL = set(PERMISSION_CATALOG)

SYSTEM_ROLES: dict[str, dict[str, object]] = {
    "owner": {
        "name": "Owner",
        "description": "Full control of the organization, including billing and security settings.",
        "permissions": ALL,
    },
    "administrator": {
        "name": "Administrator",
        "description": "Manages members, roles and all projects.",
        "permissions": ALL,
    },
    "executive": {
        "name": "Executive",
        "description": "Portfolio-wide read access to projects, financials and the audit log.",
        "permissions": {
            P.DASHBOARD_VIEW, P.PROJECTS_VIEW_ALL, P.PROJECTS_FINANCIALS_VIEW, P.COMPANIES_VIEW,
            P.DOCUMENTS_VIEW, P.MEMBERS_VIEW, P.AUDIT_VIEW, P.ESTIMATES_VIEW, P.BUDGETS_VIEW,
            P.CONTRACTS_VIEW, P.COMMITMENTS_VIEW, P.CHANGES_VIEW, P.COSTS_VIEW, P.FORECASTS_VIEW,
        },
    },
    "commercial_manager": {
        "name": "Commercial Manager",
        "description": "Manages commercial performance across all projects.",
        "permissions": {
            P.DASHBOARD_VIEW, P.PROJECTS_VIEW_ALL, P.PROJECTS_CREATE, P.PROJECTS_EDIT,
            P.PROJECTS_FINANCIALS_VIEW, P.PROJECTS_MEMBERS_MANAGE, P.COMPANIES_VIEW, P.COMPANIES_MANAGE,
            P.DOCUMENTS_VIEW, P.DOCUMENTS_UPLOAD, P.MEMBERS_VIEW, P.COST_CODES_MANAGE, P.ESTIMATES_VIEW,
            P.ESTIMATES_EDIT, P.ESTIMATES_APPROVE, P.BUDGETS_VIEW, P.BUDGETS_EDIT, P.BUDGETS_APPROVE,
            P.CONTRACTS_VIEW, P.CONTRACTS_EDIT, P.CONTRACTS_EXECUTE, P.COMMITMENTS_VIEW, P.COMMITMENTS_EDIT,
            P.COMMITMENTS_EXECUTE, P.CHANGES_VIEW, P.CHANGES_EDIT, P.CHANGES_APPROVE, P.COSTS_VIEW, P.COSTS_EDIT,
            P.FORECASTS_VIEW, P.FORECASTS_EDIT, P.FORECASTS_APPROVE,
        },
    },
    "project_manager": {
        "name": "Project Manager",
        "description": "Runs assigned projects: details, team, parties and documents.",
        "permissions": {
            P.DASHBOARD_VIEW, P.PROJECTS_CREATE, P.PROJECTS_EDIT, P.PROJECTS_FINANCIALS_VIEW,
            P.PROJECTS_MEMBERS_MANAGE, P.COMPANIES_VIEW, P.COMPANIES_MANAGE, P.DOCUMENTS_VIEW,
            P.DOCUMENTS_UPLOAD, P.MEMBERS_VIEW, P.ESTIMATES_VIEW, P.ESTIMATES_EDIT, P.BUDGETS_VIEW, P.BUDGETS_EDIT,
            P.CONTRACTS_VIEW, P.CONTRACTS_EDIT, P.COMMITMENTS_VIEW, P.COMMITMENTS_EDIT, P.CHANGES_VIEW,
            P.CHANGES_EDIT, P.COSTS_VIEW, P.FORECASTS_VIEW, P.FORECASTS_EDIT,
        },
    },
    "field_engineer": {
        "name": "Field Engineer",
        "description": "Field staff on assigned projects: view and upload documents.",
        "permissions": {P.DASHBOARD_VIEW, P.COMPANIES_VIEW, P.DOCUMENTS_VIEW, P.DOCUMENTS_UPLOAD},
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to assigned projects.",
        "permissions": {P.DASHBOARD_VIEW, P.COMPANIES_VIEW, P.DOCUMENTS_VIEW},
    },
}

# Roles that only an owner may grant (privilege-escalation guard).
OWNER_ONLY_ROLES = {"owner"}
