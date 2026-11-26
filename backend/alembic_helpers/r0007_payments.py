"""Security layer for revision 0007 (frozen): RLS, tenant-consistent FKs, lifecycle triggers, one open application
per contract, grants and permission seed."""

from __future__ import annotations

from alembic import op
from alembic_helpers.foundation_security import _app_role, _q

TABLES = ["payment_applications", "payment_application_lines"]
FKS = [
    ("payment_applications", "project_id", "projects", "CASCADE"),
    ("payment_applications", "contract_id", "contracts", "NO ACTION"),
    ("payment_application_lines", "application_id", "payment_applications", "CASCADE"),
    ("payment_application_lines", "contract_line_id", "contract_lines", "NO ACTION"),
    ("payment_application_lines", "change_order_id", "change_orders", "NO ACTION"),
    ("payment_application_lines", "cost_code_id", "cost_codes", "NO ACTION"),
]
PERMISSIONS = [
    ("payments.view", "Payments", "View payment applications / valuations"),
    ("payments.edit", "Payments", "Prepare and submit payment applications / valuations"),
    ("payments.certify", "Payments", "Record certification and payment received"),
]
_ALL = [p[0] for p in PERMISSIONS]
ROLE_GRANTS = {
    "owner": _ALL,
    "administrator": _ALL,
    "executive": ["payments.view"],
    "commercial_manager": _ALL,
    "project_manager": ["payments.view", "payments.edit"],
}

# Frozen once an application leaves draft: what was claimed, and its snapshot.
CONTENT = [
    "tenant_id",
    "project_id",
    "contract_id",
    "number",
    "currency",
    "period_to",
    "application_date",
    "due_date",
    "final_payment_date",
    "pay_less_notice_date",
    "retention_percent",
    "notes",
    "original_sum",
    "net_changes",
    "work_to_date",
    "materials_stored",
    "retention_to_date",
    "previous_certified",
    "amount_due",
]
CERTIFICATION = ["certified_amount", "certified_date", "certification_note", "certified_by_id"]


def upgrade_security() -> None:
    app = _app_role()
    ex = op.execute
    ex("ALTER TABLE payment_applications ADD CONSTRAINT uq_payment_applications_tenant_id_id UNIQUE (tenant_id, id)")
    ex("ALTER TABLE contract_lines ADD CONSTRAINT uq_contract_lines_tenant_id_id UNIQUE (tenant_id, id)")
    for child, column, parent, on_delete in FKS:
        ex(
            f"ALTER TABLE {child} ADD CONSTRAINT fk_{child}_{column}_tenant FOREIGN KEY (tenant_id, {column}) "
            f"REFERENCES {parent} (tenant_id, id) ON DELETE {on_delete}"
        )
    ex(
        "CREATE UNIQUE INDEX uq_payment_applications_one_open ON payment_applications (contract_id) "
        "WHERE status IN ('draft', 'submitted')"
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
    new_cert = ", ".join(f"NEW.{c}" for c in CERTIFICATION)
    old_cert = ", ".join(f"OLD.{c}" for c in CERTIFICATION)
    ex(f"""
    CREATE FUNCTION payment_applications_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'paid' THEN
        RAISE EXCEPTION 'application % is paid and cannot be changed', OLD.number;
      END IF;
      IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
          RAISE EXCEPTION 'only draft applications can be deleted';
        END IF;
        RETURN OLD;
      END IF;
      IF OLD.status = 'draft' THEN
        IF NEW.status NOT IN ('draft', 'submitted') THEN
          RAISE EXCEPTION 'a draft application must be submitted before it is certified';
        END IF;
        RETURN NEW;
      END IF;
      IF ROW({new_row}) IS DISTINCT FROM ROW({old_row}) THEN
        RAISE EXCEPTION 'application % is %; its claim cannot be changed', OLD.number, OLD.status;
      END IF;
      IF OLD.status = 'submitted' AND NEW.status NOT IN ('submitted', 'draft', 'certified') THEN
        RAISE EXCEPTION 'a submitted application must be certified before payment is recorded';
      END IF;
      IF OLD.status = 'certified' THEN
        IF NEW.status NOT IN ('certified', 'paid') THEN
          RAISE EXCEPTION 'a certified application cannot go back';
        END IF;
        IF ROW({new_cert}) IS DISTINCT FROM ROW({old_cert}) THEN
          RAISE EXCEPTION 'the certificate for application % cannot be changed', OLD.number;
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER payment_applications_frozen BEFORE UPDATE OR DELETE ON payment_applications
        FOR EACH ROW EXECUTE FUNCTION payment_applications_guard();

    CREATE FUNCTION payment_application_lines_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_status text;
    BEGIN
      SELECT status INTO v_status FROM payment_applications
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.application_id ELSE NEW.application_id END;
      IF v_status IS NULL AND TG_OP = 'DELETE' THEN
        RETURN OLD;  -- cascade from deleting a draft application
      END IF;
      IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'application is % and its lines cannot be changed', coalesce(v_status, 'missing');
      END IF;
      IF TG_OP = 'UPDATE' AND NEW.application_id <> OLD.application_id THEN
        RAISE EXCEPTION 'lines cannot move between applications';
      END IF;
      RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    CREATE TRIGGER payment_application_lines_frozen BEFORE INSERT OR UPDATE OR DELETE ON payment_application_lines
        FOR EACH ROW EXECUTE FUNCTION payment_application_lines_guard();
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
    ex("DROP INDEX IF EXISTS uq_payment_applications_one_open")
    for child, column, _parent, _ in FKS:
        ex(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS fk_{child}_{column}_tenant")
    ex("ALTER TABLE payment_applications DROP CONSTRAINT IF EXISTS uq_payment_applications_tenant_id_id")
    ex("ALTER TABLE contract_lines DROP CONSTRAINT IF EXISTS uq_contract_lines_tenant_id_id")
