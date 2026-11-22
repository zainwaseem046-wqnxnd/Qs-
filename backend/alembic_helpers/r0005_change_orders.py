"""Security layer for revision 0005 (frozen): RLS, tenant-consistent FKs, lifecycle triggers, grants, permissions."""

from __future__ import annotations

from alembic import op
from alembic_helpers.foundation_security import _app_role, _q

TABLES = ["change_orders", "change_order_lines"]
FKS = [
    ("change_orders", "project_id", "projects", "CASCADE"),
    ("change_orders", "contract_id", "contracts", "NO ACTION"),
    ("change_orders", "commitment_id", "commitments", "NO ACTION"),
    ("change_order_lines", "change_order_id", "change_orders", "CASCADE"),
    ("change_order_lines", "cost_code_id", "cost_codes", "NO ACTION"),
]
PERMISSIONS = [
    ("change_orders.view", "Change orders", "View change orders / variations"),
    ("change_orders.edit", "Change orders", "Create, price and submit change orders / variations"),
    ("change_orders.approve", "Change orders", "Approve or reject change orders / variations"),
]
_ALL = [p[0] for p in PERMISSIONS]
ROLE_GRANTS = {
    "owner": _ALL,
    "administrator": _ALL,
    "executive": ["change_orders.view"],
    "commercial_manager": _ALL,
    "project_manager": ["change_orders.view", "change_orders.edit"],
}

# Content columns: frozen once a change order leaves draft.
CONTENT = [
    "tenant_id",
    "project_id",
    "contract_id",
    "commitment_id",
    "number",
    "title",
    "description",
    "reason",
    "reference",
    "schedule_impact_days",
    "notified_date",
    "response_due_date",
]


def upgrade_security() -> None:
    app = _app_role()
    ex = op.execute
    ex("ALTER TABLE change_orders ADD CONSTRAINT uq_change_orders_tenant_id_id UNIQUE (tenant_id, id)")
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
    new_row = ", ".join(f"NEW.{c}" for c in CONTENT)
    old_row = ", ".join(f"OLD.{c}" for c in CONTENT)
    ex(f"""
    CREATE FUNCTION change_orders_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status IN ('approved', 'rejected', 'withdrawn') THEN
        RAISE EXCEPTION 'change order % is % and cannot be changed', OLD.number, OLD.status;
      END IF;
      IF OLD.status = 'submitted' THEN
        IF TG_OP = 'DELETE' THEN
          RAISE EXCEPTION 'submitted change orders cannot be deleted';
        END IF;
        IF ROW({new_row}) IS DISTINCT FROM ROW({old_row}) THEN
          RAISE EXCEPTION 'change order % is submitted; return it to draft to change it', OLD.number;
        END IF;
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER change_orders_frozen BEFORE UPDATE OR DELETE ON change_orders
        FOR EACH ROW EXECUTE FUNCTION change_orders_guard();

    CREATE FUNCTION change_order_lines_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM change_orders
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.change_order_id ELSE NEW.change_order_id END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN
        RETURN OLD;  -- cascade from deleting a draft change order
      END IF;
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'change order is % and its lines cannot be changed', coalesce(v_status, 'missing');
      END IF;
      IF TG_OP = 'UPDATE' AND NEW.change_order_id <> OLD.change_order_id THEN
        RAISE EXCEPTION 'lines cannot move between change orders';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER change_order_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON change_order_lines
        FOR EACH ROW EXECUTE FUNCTION change_order_lines_guard();
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
    for table in TABLES:
        ex(f"DROP TRIGGER IF EXISTS {table}_frozen ON {table}")
        ex(f"DROP FUNCTION IF EXISTS {table}_guard()")
    for child, column, _parent, _ in FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    ex("ALTER TABLE change_orders DROP CONSTRAINT IF EXISTS uq_change_orders_tenant_id_id")
