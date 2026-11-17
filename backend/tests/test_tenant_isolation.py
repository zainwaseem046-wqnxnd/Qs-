"""Tenant isolation: users must never read or write another tenant's records.

Tested at two layers: through the API, and directly against PostgreSQL as the runtime role to prove
Row-Level Security holds even if application-layer filtering were bypassed.
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.core.config import get_settings
from tests.conftest import Account, make_project, register

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def two_tenants(client):  # type: ignore[no-untyped-def]
    a = register(client, org="Alpha Contractors")
    b = register(client, org="Bravo Builders")
    return a, b


def _seed(acct: Account) -> dict[str, str]:
    project = make_project(acct)
    company = acct.post("/api/v1/companies", json={"name": "Secret Sub LLC", "company_type": "subcontractor"}).json()
    doc = acct.post("/api/v1/documents", data={"title": "Confidential GMP", "category": "contract",
                                               "project_id": project["id"]},
                    files={"file": ("gmp.pdf", io.BytesIO(PDF), "application/pdf")}).json()
    return {"project": project["id"], "company": company["id"], "document": doc["id"]}


def test_api_cross_tenant_reads_return_404(two_tenants) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    ids = _seed(b)
    assert a.get(f"/api/v1/projects/{ids['project']}").status_code == 404
    assert a.get(f"/api/v1/companies/{ids['company']}").status_code == 404
    assert a.get(f"/api/v1/documents/{ids['document']}").status_code == 404
    assert a.get(f"/api/v1/documents/{ids['document']}/versions/1/download").status_code == 404
    assert a.get(f"/api/v1/projects/{ids['project']}/activity").status_code == 404
    listing = a.get("/api/v1/projects").json()
    assert all(p["id"] != ids["project"] for p in listing["items"])
    assert a.get("/api/v1/companies").json()["total"] == 0
    audit = a.get("/api/v1/audit-events").json()["items"]
    assert all(e["project_id"] != ids["project"] for e in audit)


def test_api_cross_tenant_writes_rejected(two_tenants) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    ids = _seed(b)
    assert a.patch(f"/api/v1/projects/{ids['project']}", json={"version": 1, "name": "Hijacked"}).status_code == 404
    assert a.post(f"/api/v1/projects/{ids['project']}/archive").status_code == 404
    assert a.delete(f"/api/v1/documents/{ids['document']}").status_code == 404
    assert a.patch(f"/api/v1/companies/{ids['company']}", json={"version": 1, "name": "x"}).status_code == 404
    # Referencing another tenant's company from your own project is rejected.
    resp = a.post("/api/v1/projects", json={"number": "X-1", "name": "Mine", "sector": "commercial",
                                            "delivery_method": "design_build", "contract_type": "lump_sum",
                                            "client_company_id": ids["company"]})
    assert resp.status_code == 422
    # Uploading a document into another tenant's project is rejected.
    up = a.post("/api/v1/documents", data={"title": "x", "category": "other", "project_id": ids["project"]},
                files={"file": ("x.pdf", io.BytesIO(PDF), "application/pdf")})
    assert up.status_code == 404
    # B's data is unchanged.
    assert b.get(f"/api/v1/projects/{ids['project']}").json()["name"] != "Hijacked"


def test_cannot_act_in_tenant_without_membership(two_tenants) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    spoof = Account(a.client, a.email, a.user_id, b.tenant_id, a.token)
    for resp in (spoof.get("/api/v1/projects"), spoof.get("/api/v1/tenant"),
                 spoof.post("/api/v1/projects", json={})):
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "tenant_forbidden"
    random_tenant = Account(a.client, a.email, a.user_id, str(uuid.uuid4()), a.token)
    assert random_tenant.get("/api/v1/projects").json()["error"]["code"] == "tenant_forbidden"
    assert a.client.get("/api/v1/projects", headers={"Authorization": f"Bearer {a.token}"}).status_code == 403


# --- database-level RLS ------------------------------------------------------------------------
@pytest.fixture
def app_engine():  # type: ignore[no-untyped-def]
    engine = create_engine(get_settings().database_url)
    yield engine
    engine.dispose()


def _ctx(conn, tenant_id: str | None, user_id: str | None = None) -> None:  # type: ignore[no-untyped-def]
    conn.execute(text("SELECT set_config('app.tenant_id', :t, true), set_config('app.user_id', :u, true)"),
                 {"t": tenant_id or "", "u": user_id or ""})


def test_rls_blocks_reads_without_or_with_wrong_context(two_tenants, app_engine) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    _seed(b)
    with app_engine.begin() as conn:
        for table in ("projects", "companies", "documents", "document_versions", "addresses", "audit_events"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table
        _ctx(conn, a.tenant_id, a.user_id)
        assert conn.execute(text("SELECT count(*) FROM projects WHERE tenant_id = :t"),
                            {"t": b.tenant_id}).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM tenants WHERE id = :t"), {"t": b.tenant_id}).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM users WHERE id = :u"), {"u": b.user_id}).scalar() == 0
        _ctx(conn, b.tenant_id, b.user_id)
        assert conn.execute(text("SELECT count(*) FROM projects")).scalar() >= 1


def test_rls_blocks_cross_tenant_insert(two_tenants, app_engine) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    with app_engine.connect() as conn, pytest.raises((ProgrammingError, DBAPIError)) as exc:
        trans = conn.begin()
        _ctx(conn, a.tenant_id, a.user_id)
        conn.execute(text(
            "INSERT INTO companies (id, tenant_id, name, company_type) VALUES (gen_random_uuid(), :t, 'x', 'other')"
        ), {"t": b.tenant_id})
        trans.rollback()
    assert "row-level security" in str(exc.value)


def test_composite_fk_blocks_cross_tenant_reference(two_tenants, app_engine) -> None:  # type: ignore[no-untyped-def]
    a, b = two_tenants
    ids = _seed(b)
    with app_engine.connect() as conn, pytest.raises(IntegrityError):
        trans = conn.begin()
        _ctx(conn, a.tenant_id, a.user_id)
        conn.execute(text(
            "INSERT INTO projects (id, tenant_id, number, name, status, sector, delivery_method, contract_type, "
            "our_role, client_company_id) VALUES (gen_random_uuid(), :t, 'FK-1', 'x', 'active', 'commercial', "
            "'design_build', 'lump_sum', 'general_contractor', :c)"
        ), {"t": a.tenant_id, "c": ids["company"]})
        trans.rollback()


def test_runtime_role_cannot_bypass_rls_or_alter_schema(app_engine) -> None:  # type: ignore[no-untyped-def]
    with app_engine.connect() as conn:
        row = conn.execute(text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")).one()
        assert row == (False, False)
        with pytest.raises(ProgrammingError):
            conn.execute(text("ALTER TABLE projects DISABLE ROW LEVEL SECURITY"))
        conn.rollback()
        with pytest.raises(ProgrammingError):
            conn.execute(text("DELETE FROM permissions"))
        conn.rollback()
