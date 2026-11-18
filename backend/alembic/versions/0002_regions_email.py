"""US + UK markets and email: tenant country/data region, password reset tokens.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from alembic_helpers.foundation_security import _app_role

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    app = _app_role()
    op.add_column("tenants", sa.Column("country_code", sa.String(2), server_default="US", nullable=False))
    op.add_column("tenants", sa.Column("data_region", sa.String(2), server_default="us", nullable=False))
    op.create_check_constraint("country_code_supported", "tenants", "country_code IN ('US', 'GB')")
    op.create_check_constraint("data_region_supported", "tenants", "data_region IN ('us', 'uk')")
    op.create_check_constraint(
        "measurement_system_supported", "tenants", "measurement_system IN ('us_customary', 'metric')"
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])
    op.execute("""
    ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
    CREATE POLICY password_reset_own ON password_reset_tokens FOR ALL
        USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user());
    CREATE FUNCTION auth_find_password_reset_by_token_hash(p_hash text) RETURNS SETOF password_reset_tokens
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
    $$ SELECT * FROM password_reset_tokens WHERE token_hash = p_hash $$;
    REVOKE ALL ON FUNCTION auth_find_password_reset_by_token_hash(text) FROM PUBLIC;
    """)
    op.execute(f"GRANT EXECUTE ON FUNCTION auth_find_password_reset_by_token_hash(text) TO {app}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON password_reset_tokens TO {app}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS auth_find_password_reset_by_token_hash(text)")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_constraint(op.f("ck_tenants_measurement_system_supported"), "tenants", type_="check")
    op.drop_constraint(op.f("ck_tenants_data_region_supported"), "tenants", type_="check")
    op.drop_constraint(op.f("ck_tenants_country_code_supported"), "tenants", type_="check")
    op.drop_column("tenants", "data_region")
    op.drop_column("tenants", "country_code")
