"""Security layer for revision 0003 (frozen): RLS, tenant-consistent FKs, immutability triggers, grants,
and the Phase 2.1 permission seed."""

from __future__ import annotations

from alembic import op
from alembic_helpers.foundation_security import _app_role, _q

TABLES = [
    "cost_code_sets",
    "cost_codes",
    "estimates",
    "estimate_versions",
    "estimate_lines",
    "estimate_markups",
    "budgets",
    "budget_lines",
]
PARENTS = ["cost_code_sets", "cost_codes", "estimates", "estimate_versions", "budgets"]
FKS = [
    ("cost_codes", "set_id", "cost_code_sets", "CASCADE"),
    ("cost_codes", "parent_id", "cost_codes", "NO ACTION"),
    ("estimates", "project_id", "projects", "CASCADE"),
    ("estimates", "cost_code_set_id", "cost_code_sets", "NO ACTION"),
    ("estimate_versions", "estimate_id", "estimates", "CASCADE"),
    ("estimate_lines", "version_id", "estimate_versions", "CASCADE"),
    ("estimate_lines", "cost_code_id", "cost_codes", "NO ACTION"),
    ("estimate_markups", "version_id", "estimate_versions", "CASCADE"),
    ("budgets", "project_id", "projects", "CASCADE"),
    ("budgets", "cost_code_set_id", "cost_code_sets", "NO ACTION"),
    ("budgets", "source_estimate_version_id", "estimate_versions", "NO ACTION"),
    ("budget_lines", "budget_id", "budgets", "CASCADE"),
    ("budget_lines", "cost_code_id", "cost_codes", "NO ACTION"),
]

PERMISSIONS = [
    ("cost_codes.manage", "Commercial", "Create and import cost code structures"),
    ("estimates.view", "Commercial", "View estimates"),
    ("estimates.edit", "Commercial", "Create and edit draft estimates"),
    ("estimates.approve", "Commercial", "Approve issued estimates"),
    ("budgets.view", "Commercial", "View project budgets"),
    ("budgets.edit", "Commercial", "Create and edit draft budgets"),
    ("budgets.approve", "Commercial", "Approve original budgets"),
]
_ALL = [p[0] for p in PERMISSIONS]
ROLE_GRANTS = {
    "owner": _ALL,
    "administrator": _ALL,
    "executive": ["estimates.view", "budgets.view"],
    "commercial_manager": _ALL,
    "project_manager": ["estimates.view", "estimates.edit", "budgets.view", "budgets.edit"],
}


def upgrade_security() -> None:
    app = _app_role()
    ex = op.execute
    for parent in PARENTS:
        ex(f"ALTER TABLE {parent} ADD CONSTRAINT uq_{parent}_tenant_id_id UNIQUE (tenant_id, id)")
    for child, column, parent, on_delete in FKS:
        ex(
            f"ALTER TABLE {child} ADD CONSTRAINT fk_{child}_{column}_tenant FOREIGN KEY (tenant_id, {column}) "
            f"REFERENCES {parent} (tenant_id, id) ON DELETE {on_delete}"
        )
    for table in TABLES:
        ex(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        ex(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = app_current_tenant()) "
            f"WITH CHECK (tenant_id = app_current_tenant())"
        )
        ex(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {app}")

    # Issued/approved estimate versions are frozen; only issued -> approved is permitted.
    ex("""
    CREATE FUNCTION estimate_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'draft' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
      END IF;
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'estimate version % is % and cannot be deleted', OLD.version_number, OLD.status;
      END IF;
      IF OLD.status = 'issued' AND NEW.status = 'approved'
         AND ROW(NEW.estimate_id, NEW.version_number, NEW.label, NEW.notes, NEW.price_base_date, NEW.direct_cost,
                 NEW.markup_total, NEW.total, NEW.issued_at, NEW.issued_by_id, NEW.revision, NEW.tenant_id)
             IS NOT DISTINCT FROM
             ROW(OLD.estimate_id, OLD.version_number, OLD.label, OLD.notes, OLD.price_base_date, OLD.direct_cost,
                 OLD.markup_total, OLD.total, OLD.issued_at, OLD.issued_by_id, OLD.revision, OLD.tenant_id) THEN
        RETURN NEW;
      END IF;
      RAISE EXCEPTION 'estimate version % is % and cannot be changed', OLD.version_number, OLD.status;
    END $$;
    CREATE TRIGGER estimate_versions_frozen BEFORE UPDATE OR DELETE ON estimate_versions
        FOR EACH ROW EXECUTE FUNCTION estimate_version_guard();

    CREATE FUNCTION estimate_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM estimate_versions
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.version_id ELSE NEW.version_id END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN
        RETURN OLD;  -- cascade from deleting a draft version (frozen versions cannot be deleted)
      END IF;
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'estimate version is % and cannot be changed', coalesce(v_status, 'missing');
      END IF;
      IF TG_OP = 'UPDATE' AND NEW.version_id <> OLD.version_id THEN
        RAISE EXCEPTION 'estimate rows cannot move between versions';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER estimate_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON estimate_lines
        FOR EACH ROW EXECUTE FUNCTION estimate_child_guard();
    CREATE TRIGGER estimate_markups_frozen BEFORE INSERT OR UPDATE OR DELETE ON estimate_markups
        FOR EACH ROW EXECUTE FUNCTION estimate_child_guard();

    CREATE FUNCTION budget_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'approved' THEN
        RAISE EXCEPTION 'approved budgets cannot be changed; use budget transfers or change orders';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER budgets_frozen BEFORE UPDATE OR DELETE ON budgets
        FOR EACH ROW EXECUTE FUNCTION budget_guard();

    CREATE FUNCTION budget_line_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM budgets
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.budget_id ELSE NEW.budget_id END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN
        RETURN OLD;  -- cascade from deleting a draft budget (approved budgets cannot be deleted)
      END IF;
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'budget is % and its lines cannot be changed', coalesce(v_status, 'missing');
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER budget_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON budget_lines
        FOR EACH ROW EXECUTE FUNCTION budget_line_guard();
    """)

    values = ", ".join(f"({_q(k)}, {_q(d)}, {_q(c)})" for k, c, d in PERMISSIONS)
    ex(f"INSERT INTO permissions (key, description, category) VALUES {values}")
    for role, perms in ROLE_GRANTS.items():
        perm_list = ", ".join(_q(p) for p in perms)
        ex(
            f"INSERT INTO role_permissions (role_id, permission_key) SELECT r.id, p.key FROM roles r "
            f"CROSS JOIN permissions p WHERE r.tenant_id IS NULL AND r.key = {_q(role)} AND p.key IN ({perm_list})"
        )


def downgrade_security() -> None:
    ex = op.execute
    keys = ", ".join(_q(p[0]) for p in PERMISSIONS)
    ex(f"DELETE FROM role_permissions WHERE permission_key IN ({keys})")
    ex(f"DELETE FROM permissions WHERE key IN ({keys})")
    for trig, table in [
        ("estimate_versions_frozen", "estimate_versions"),
        ("estimate_lines_frozen", "estimate_lines"),
        ("estimate_markups_frozen", "estimate_markups"),
        ("budgets_frozen", "budgets"),
        ("budget_lines_frozen", "budget_lines"),
    ]:
        ex(f"DROP TRIGGER IF EXISTS {trig} ON {table}")
    for fn in ("estimate_version_guard", "estimate_child_guard", "budget_guard", "budget_line_guard"):
        ex(f"DROP FUNCTION IF EXISTS {fn}()")
    for child, column, _parent, _ in FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    for parent in PARENTS:
        ex(f"ALTER TABLE {parent} DROP CONSTRAINT IF EXISTS uq_{parent}_tenant_id_id")
