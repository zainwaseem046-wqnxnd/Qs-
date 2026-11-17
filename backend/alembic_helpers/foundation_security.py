"""Security layer for revision 0001 (frozen).

* RLS policies keyed on transaction-local settings ``app.tenant_id`` / ``app.user_id``.
* Composite (tenant_id, id) foreign keys so a row can never reference another tenant's row.
* Append-only audit_events and immutable document version content.
* SECURITY DEFINER lookups for the few pre-authentication queries (login, refresh, invitation).
* Least-privilege grants for the runtime role.
* Frozen seed of the Phase 1 permission catalog and system roles.
"""

from __future__ import annotations

import re

from alembic import op
from app.core.config import get_settings

STANDARD_TENANT_TABLES = [
    "addresses",
    "companies",
    "contacts",
    "projects",
    "project_members",
    "project_parties",
    "project_phases",
    "documents",
    "document_versions",
    "invitations",
]

# (child_table, child_column, parent_table, on_delete_clause)
TENANT_CONSISTENT_FKS = [
    ("companies", "address_id", "addresses", "SET NULL (address_id)"),
    ("contacts", "company_id", "companies", "CASCADE"),
    ("projects", "client_company_id", "companies", "SET NULL (client_company_id)"),
    ("projects", "site_address_id", "addresses", "SET NULL (site_address_id)"),
    ("project_members", "project_id", "projects", "CASCADE"),
    ("project_parties", "project_id", "projects", "CASCADE"),
    ("project_parties", "company_id", "companies", "CASCADE"),
    ("project_phases", "project_id", "projects", "CASCADE"),
    ("documents", "project_id", "projects", "CASCADE"),
    ("document_versions", "document_id", "documents", "CASCADE"),
]

PERMISSIONS = [
    ("tenant.manage", "Organization", "Manage organization settings"),
    ("members.view", "Organization", "View organization members"),
    ("members.manage", "Organization", "Invite, suspend and change roles of members"),
    ("roles.manage", "Organization", "Create and edit custom roles"),
    ("audit.view", "Organization", "View the organization audit log"),
    ("dashboard.view", "Dashboard", "View the executive dashboard"),
    ("projects.view_all", "Projects", "View all projects (not only assigned projects)"),
    ("projects.create", "Projects", "Create projects"),
    ("projects.edit", "Projects", "Edit project details, parties and phases"),
    ("projects.archive", "Projects", "Archive and restore projects"),
    ("projects.members.manage", "Projects", "Manage project team membership"),
    ("projects.financials.view", "Projects", "View contract values and commercial figures"),
    ("companies.view", "Directory", "View companies and contacts"),
    ("companies.manage", "Directory", "Create and edit companies and contacts"),
    ("documents.view", "Documents", "View and download documents"),
    ("documents.upload", "Documents", "Upload documents and new versions"),
    ("documents.delete", "Documents", "Delete documents"),
]
_ALL = [p[0] for p in PERMISSIONS]

SYSTEM_ROLES = [
    ("owner", "Owner", "Full control of the organization, including billing and security settings.", _ALL),
    ("administrator", "Administrator", "Manages members, roles and all projects.", _ALL),
    ("executive", "Executive", "Portfolio-wide read access to projects, financials and the audit log.",
     ["dashboard.view", "projects.view_all", "projects.financials.view", "companies.view",
      "documents.view", "members.view", "audit.view"]),
    ("commercial_manager", "Commercial Manager", "Manages commercial performance across all projects.",
     ["dashboard.view", "projects.view_all", "projects.create", "projects.edit", "projects.financials.view",
      "projects.members.manage", "companies.view", "companies.manage", "documents.view", "documents.upload",
      "members.view"]),
    ("project_manager", "Project Manager", "Runs assigned projects: details, team, parties and documents.",
     ["dashboard.view", "projects.create", "projects.edit", "projects.financials.view",
      "projects.members.manage", "companies.view", "companies.manage", "documents.view", "documents.upload",
      "members.view"]),
    ("field_engineer", "Field Engineer", "Field staff on assigned projects: view and upload documents.",
     ["dashboard.view", "companies.view", "documents.view", "documents.upload"]),
    ("viewer", "Viewer", "Read-only access to assigned projects.",
     ["dashboard.view", "companies.view", "documents.view"]),
]


def _app_role() -> str:
    role = get_settings().app_db_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError("Invalid QS_APP_DB_ROLE")
    return role


def _q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade_security() -> None:
    app = _app_role()
    ex = op.execute

    # --- context helpers ----------------------------------------------------------------------
    ex("""
    CREATE FUNCTION app_current_tenant() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;
    CREATE FUNCTION app_current_user() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
    """)

    # --- tenant-consistent composite foreign keys --------------------------------------------
    for parent in sorted({fk[2] for fk in TENANT_CONSISTENT_FKS}):
        ex(f"ALTER TABLE {parent} ADD CONSTRAINT uq_{parent}_tenant_id_id UNIQUE (tenant_id, id)")
    for child, column, parent, on_delete in TENANT_CONSISTENT_FKS:
        ex(
            f"ALTER TABLE {child} ADD CONSTRAINT fk_{child}_{column}_tenant FOREIGN KEY (tenant_id, {column}) "
            f"REFERENCES {parent} (tenant_id, id) ON DELETE {on_delete}"
        )

    # --- standard tenant isolation policies ---------------------------------------------------
    for table in STANDARD_TENANT_TABLES:
        ex(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        ex(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = app_current_tenant()) "
            f"WITH CHECK (tenant_id = app_current_tenant())"
        )

    ex("""
    ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
    CREATE POLICY tenants_select ON tenants FOR SELECT USING (
        id = app_current_tenant()
        OR EXISTS (SELECT 1 FROM tenant_memberships m
                   WHERE m.tenant_id = tenants.id AND m.user_id = app_current_user() AND m.status = 'active'));
    CREATE POLICY tenants_insert ON tenants FOR INSERT WITH CHECK (id = app_current_tenant());
    CREATE POLICY tenants_update ON tenants FOR UPDATE USING (id = app_current_tenant())
        WITH CHECK (id = app_current_tenant());

    ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
    CREATE POLICY memberships_select ON tenant_memberships FOR SELECT
        USING (tenant_id = app_current_tenant() OR user_id = app_current_user());
    CREATE POLICY memberships_write ON tenant_memberships FOR ALL
        USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant());

    ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
    CREATE POLICY roles_select ON roles FOR SELECT USING (tenant_id IS NULL OR tenant_id = app_current_tenant());
    CREATE POLICY roles_write ON roles FOR ALL
        USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant());

    ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
    CREATE POLICY role_permissions_select ON role_permissions FOR SELECT
        USING (EXISTS (SELECT 1 FROM roles r WHERE r.id = role_permissions.role_id));
    CREATE POLICY role_permissions_write ON role_permissions FOR ALL
        USING (EXISTS (SELECT 1 FROM roles r WHERE r.id = role_permissions.role_id
                       AND r.tenant_id = app_current_tenant()))
        WITH CHECK (EXISTS (SELECT 1 FROM roles r WHERE r.id = role_permissions.role_id
                            AND r.tenant_id = app_current_tenant()));

    ALTER TABLE users ENABLE ROW LEVEL SECURITY;
    CREATE POLICY users_select ON users FOR SELECT USING (
        id = app_current_user()
        OR EXISTS (SELECT 1 FROM tenant_memberships m
                   WHERE m.user_id = users.id AND m.tenant_id = app_current_tenant()));
    CREATE POLICY users_insert ON users FOR INSERT WITH CHECK (true);
    CREATE POLICY users_update ON users FOR UPDATE USING (id = app_current_user())
        WITH CHECK (id = app_current_user());

    ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;
    CREATE POLICY auth_sessions_own ON auth_sessions FOR ALL
        USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user());

    ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
    CREATE POLICY audit_select ON audit_events FOR SELECT USING (tenant_id = app_current_tenant());
    CREATE POLICY audit_insert ON audit_events FOR INSERT
        WITH CHECK (tenant_id IS NULL OR tenant_id = app_current_tenant());
    """)

    # --- immutability ---------------------------------------------------------------------------
    ex("""
    CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'audit_events is append-only'; END $$;
    CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
    CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

    CREATE FUNCTION document_versions_content_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.storage_key IS DISTINCT FROM OLD.storage_key OR NEW.sha256 IS DISTINCT FROM OLD.sha256
         OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes OR NEW.version_number IS DISTINCT FROM OLD.version_number
         OR NEW.document_id IS DISTINCT FROM OLD.document_id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION 'document version content is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER document_versions_immutable BEFORE UPDATE ON document_versions
        FOR EACH ROW EXECUTE FUNCTION document_versions_content_immutable();
    """)

    # --- pre-authentication lookups (SECURITY DEFINER, owner bypasses RLS) --------------------
    ex("""
    CREATE FUNCTION auth_find_user_by_email(p_email text) RETURNS SETOF users
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
    $$ SELECT * FROM users WHERE lower(email) = lower(p_email) $$;

    CREATE FUNCTION auth_find_session_by_token_hash(p_hash text) RETURNS SETOF auth_sessions
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
    $$ SELECT * FROM auth_sessions WHERE token_hash = p_hash $$;

    CREATE FUNCTION auth_find_invitation_by_token_hash(p_hash text) RETURNS SETOF invitations
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
    $$ SELECT * FROM invitations WHERE token_hash = p_hash $$;

    CREATE FUNCTION auth_tenant_slug_exists(p_slug text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
    $$ SELECT EXISTS (SELECT 1 FROM tenants WHERE slug = p_slug) $$;
    """)
    for fn in ("auth_find_user_by_email(text)", "auth_find_session_by_token_hash(text)",
               "auth_find_invitation_by_token_hash(text)", "auth_tenant_slug_exists(text)"):
        ex(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        ex(f"GRANT EXECUTE ON FUNCTION {fn} TO {app}")

    # --- grants (least privilege) ---------------------------------------------------------------
    ex(f"GRANT SELECT ON permissions TO {app}")
    ex(f"GRANT SELECT, INSERT, UPDATE ON tenants TO {app}")
    ex(f"GRANT SELECT, INSERT ON audit_events TO {app}")
    ex(f"GRANT SELECT, INSERT, UPDATE ON document_versions TO {app}")
    for table in ["users", "auth_sessions", "roles", "role_permissions", "tenant_memberships", "addresses",
                  "companies", "contacts", "projects", "project_members", "project_parties", "project_phases",
                  "documents", "invitations"]:
        ex(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {app}")

    # --- frozen seed -----------------------------------------------------------------------------
    values = ", ".join(f"({_q(k)}, {_q(d)}, {_q(c)})" for k, c, d in PERMISSIONS)
    ex(f"INSERT INTO permissions (key, description, category) VALUES {values}")
    for key, name, description, perms in SYSTEM_ROLES:
        ex(
            f"INSERT INTO roles (id, tenant_id, key, name, description, is_system) "
            f"VALUES (gen_random_uuid(), NULL, {_q(key)}, {_q(name)}, {_q(description)}, true)"
        )
        perm_list = ", ".join(_q(p) for p in perms)
        ex(
            f"INSERT INTO role_permissions (role_id, permission_key) SELECT r.id, p.key FROM roles r "
            f"CROSS JOIN permissions p WHERE r.tenant_id IS NULL AND r.key = {_q(key)} AND p.key IN ({perm_list})"
        )


def downgrade_security() -> None:
    ex = op.execute
    for fn in ("auth_find_user_by_email(text)", "auth_find_session_by_token_hash(text)",
               "auth_find_invitation_by_token_hash(text)", "auth_tenant_slug_exists(text)"):
        ex(f"DROP FUNCTION IF EXISTS {fn}")
    ex("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
    ex("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
    ex("DROP TRIGGER IF EXISTS document_versions_immutable ON document_versions")
    ex("DROP FUNCTION IF EXISTS audit_events_immutable()")
    ex("DROP FUNCTION IF EXISTS document_versions_content_immutable()")
    for child, column, _parent, _ in TENANT_CONSISTENT_FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    for parent in sorted({fk[2] for fk in TENANT_CONSISTENT_FKS}):
        ex(f"ALTER TABLE {parent} DROP CONSTRAINT IF EXISTS uq_{parent}_tenant_id_id")
    # Policies are dropped with their tables; functions used by policies are dropped last via CASCADE.
    ex("DROP FUNCTION IF EXISTS app_current_tenant() CASCADE")
    ex("DROP FUNCTION IF EXISTS app_current_user() CASCADE")
