"""Security layer for revision 0006 (frozen): RLS, tenant-consistent FKs, immutable ledger, forecast freeze,
grants and permission seed."""

from __future__ import annotations

from alembic import op
from alembic_helpers.foundation_security import _app_role, _q

TABLES = ["cost_import_batches", "cost_transactions", "forecasts", "forecast_lines"]
PARENTS = ["cost_import_batches", "cost_transactions", "forecasts"]
FKS = [
    ("cost_import_batches", "project_id", "projects", "CASCADE"),
    ("cost_transactions", "project_id", "projects", "CASCADE"),
    ("cost_transactions", "cost_code_id", "cost_codes", "NO ACTION"),
    ("cost_transactions", "commitment_id", "commitments", "NO ACTION"),
    ("cost_transactions", "vendor_company_id", "companies", "NO ACTION"),
    ("cost_transactions", "reverses_id", "cost_transactions", "NO ACTION"),
    ("cost_transactions", "import_batch_id", "cost_import_batches", "NO ACTION"),
    ("forecasts", "project_id", "projects", "CASCADE"),
    ("forecast_lines", "forecast_id", "forecasts", "CASCADE"),
    ("forecast_lines", "cost_code_id", "cost_codes", "NO ACTION"),
]
PERMISSIONS = [
    ("costs.view", "Cost management", "View actual cost and accruals"),
    ("costs.edit", "Cost management", "Post, import and reverse cost transactions"),
    ("forecasts.view", "Cost management", "View forecasts"),
    ("forecasts.edit", "Cost management", "Prepare draft forecasts"),
    ("forecasts.approve", "Cost management", "Approve forecasts"),
]
_ALL = [p[0] for p in PERMISSIONS]
ROLE_GRANTS = {
    "owner": _ALL,
    "administrator": _ALL,
    "executive": ["costs.view", "forecasts.view"],
    "commercial_manager": _ALL,
    "project_manager": ["costs.view", "forecasts.view", "forecasts.edit"],
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
    # Ledger and import batches are insert-only for the runtime role.
    ex(f"GRANT SELECT, INSERT ON cost_transactions, cost_import_batches TO {app}")
    ex(f"GRANT SELECT, INSERT, UPDATE, DELETE ON forecasts, forecast_lines TO {app}")
    ex("""
    CREATE FUNCTION cost_ledger_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'the cost ledger is append-only; post a reversing entry instead'; END $$;
    CREATE TRIGGER cost_transactions_immutable BEFORE UPDATE OR DELETE ON cost_transactions
        FOR EACH ROW EXECUTE FUNCTION cost_ledger_immutable();
    CREATE TRIGGER cost_import_batches_immutable BEFORE UPDATE OR DELETE ON cost_import_batches
        FOR EACH ROW EXECUTE FUNCTION cost_ledger_immutable();

    CREATE FUNCTION forecasts_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'approved' THEN
        RAISE EXCEPTION 'approved forecasts cannot be changed; prepare next period''s forecast instead';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER forecasts_frozen BEFORE UPDATE OR DELETE ON forecasts
        FOR EACH ROW EXECUTE FUNCTION forecasts_guard();

    CREATE FUNCTION forecast_lines_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM forecasts
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.forecast_id ELSE NEW.forecast_id END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      -- the approval transaction writes the snapshot onto lines before freezing the header
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'forecast is % and its lines cannot be changed', coalesce(v_status, 'missing');
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER forecast_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON forecast_lines
        FOR EACH ROW EXECUTE FUNCTION forecast_lines_guard();
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
        ("cost_transactions_immutable", "cost_transactions"),
        ("cost_import_batches_immutable", "cost_import_batches"),
        ("forecasts_frozen", "forecasts"),
        ("forecast_lines_frozen", "forecast_lines"),
    ]:
        ex(f"DROP TRIGGER IF EXISTS {trig} ON {table}")
    for fn in ("cost_ledger_immutable", "forecasts_guard", "forecast_lines_guard"):
        ex(f"DROP FUNCTION IF EXISTS {fn}()")
    for child, column, _parent, _ in FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    for parent in PARENTS:
        ex(f"ALTER TABLE {parent} DROP CONSTRAINT IF EXISTS uq_{parent}_tenant_id_id")
