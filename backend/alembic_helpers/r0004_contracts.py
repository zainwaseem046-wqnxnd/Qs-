"""Security layer for revision 0004 (frozen): RLS, tenant-consistent FKs, execution freeze triggers, grants,
and the Phase 2.2 permission seed."""

from __future__ import annotations

from alembic import op
from alembic_helpers.foundation_security import _app_role, _q

TABLES = ["contracts", "contract_lines", "commitments", "commitment_lines"]
PARENTS = ["contracts", "commitments"]
FKS = [
    ("contracts", "project_id", "projects", "CASCADE"),
    ("contracts", "client_company_id", "companies", "NO ACTION"),
    ("contracts", "cost_code_set_id", "cost_code_sets", "NO ACTION"),
    ("commitments", "cost_code_set_id", "cost_code_sets", "NO ACTION"),
    ("contract_lines", "contract_id", "contracts", "CASCADE"),
    ("contract_lines", "cost_code_id", "cost_codes", "NO ACTION"),
    ("commitments", "project_id", "projects", "CASCADE"),
    ("commitments", "vendor_company_id", "companies", "NO ACTION"),
    ("commitment_lines", "commitment_id", "commitments", "CASCADE"),
    ("commitment_lines", "cost_code_id", "cost_codes", "NO ACTION"),
]
PERMISSIONS = [
    ("contracts.view", "Contracts", "View prime contracts with clients"),
    ("contracts.edit", "Contracts", "Create and edit draft prime contracts"),
    ("contracts.execute", "Contracts", "Execute, close and void prime contracts"),
    ("commitments.view", "Contracts", "View subcontracts and purchase orders"),
    ("commitments.edit", "Contracts", "Create and edit draft subcontracts and purchase orders"),
    ("commitments.execute", "Contracts", "Execute, close and void subcontracts and purchase orders"),
]
_ALL = [p[0] for p in PERMISSIONS]
ROLE_GRANTS = {
    "owner": _ALL,
    "administrator": _ALL,
    "executive": ["contracts.view", "commitments.view"],
    "commercial_manager": _ALL,
    "project_manager": ["contracts.view", "contracts.edit", "commitments.view", "commitments.edit"],
}

# Columns that may still change after execution (status transitions and bookkeeping only).
_MUTABLE_AFTER_EXECUTION = {"status", "closed_at", "updated_at", "version"}


def _guard_sql(table: str, columns: list[str]) -> str:
    frozen = [c for c in columns if c not in _MUTABLE_AFTER_EXECUTION]
    new_row = ", ".join(f"NEW.{c}" for c in frozen)
    old_row = ", ".join(f"OLD.{c}" for c in frozen)
    return f"""
    CREATE FUNCTION {table}_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'draft' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
      END IF;
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '{table} record is % and cannot be deleted', OLD.status;
      END IF;
      IF OLD.status = 'executed' AND NEW.status IN ('executed', 'closed')
         AND ROW({new_row}) IS NOT DISTINCT FROM ROW({old_row}) THEN
        RETURN NEW;
      END IF;
      RAISE EXCEPTION '{table} record is % and its terms cannot be changed', OLD.status;
    END $$;
    CREATE TRIGGER {table}_frozen BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION {table}_guard();
    """


def _line_guard_sql(table: str, parent: str, fk: str) -> str:
    return f"""
    CREATE FUNCTION {table}_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM {parent}
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.{fk} ELSE NEW.{fk} END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN
        RETURN OLD;  -- cascade from deleting a draft parent
      END IF;
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'parent is % and its lines cannot be changed', coalesce(v_status, 'missing');
      END IF;
      IF TG_OP = 'UPDATE' AND NEW.{fk} <> OLD.{fk} THEN
        RAISE EXCEPTION 'lines cannot move between records';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER {table}_frozen BEFORE INSERT OR UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION {table}_guard();
    """


TERMS_COLUMNS = [
    "tenant_id",
    "project_id",
    "number",
    "title",
    "contract_form",
    "currency",
    "retention_percent",
    "retention_terms",
    "payment_terms_days",
    "start_date",
    "completion_date",
    "scope_summary",
    "original_sum",
    "executed_date",
    "executed_at",
    "executed_by_id",
    "cost_code_set_id",
]
CONTRACT_COLUMNS = [
    *TERMS_COLUMNS,
    "client_company_id",
    "defects_period_months",
    "liquidated_damages_amount",
    "liquidated_damages_period",
    "bond_required",
    "bond_percent",
    "insurance_notes",
]
COMMITMENT_COLUMNS = [*TERMS_COLUMNS, "commitment_type", "vendor_company_id", "exclusions"]


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
    ex(_guard_sql("contracts", CONTRACT_COLUMNS))
    ex(_guard_sql("commitments", COMMITMENT_COLUMNS))
    ex(_line_guard_sql("contract_lines", "contracts", "contract_id"))
    ex(_line_guard_sql("commitment_lines", "commitments", "commitment_id"))

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
    for table in TABLES:
        ex(f"DROP TRIGGER IF EXISTS {table}_frozen ON {table}")
        ex(f"DROP FUNCTION IF EXISTS {table}_guard()")
    for child, column, _parent, _ in FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    for parent in PARENTS:
        ex(f"ALTER TABLE {parent} DROP CONSTRAINT IF EXISTS uq_{parent}_tenant_id_id")
