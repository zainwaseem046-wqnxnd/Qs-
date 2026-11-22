"""Phase 2.2: prime contracts, commitments (subcontracts / purchase orders), commercial summary."""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import Account, invite_and_join, make_project, register

TODAY = date.today().isoformat()
CSV = "code,title,parent_code\n03,Concrete,\n03-100,Footings,03\n05,Metals,\n05-100,Structural steel,05\n"


@pytest.fixture
def setup(owner):  # type: ignore[no-untyped-def]
    s = owner.post("/api/v1/cost-code-sets", json={"name": "Codes", "template_key": "masterformat_style"}).json()
    owner.post(f"/api/v1/cost-code-sets/{s['id']}/import", files={"file": ("c.csv", io.BytesIO(CSV.encode()), "text/csv")})
    codes = {c["code"]: c["id"] for c in owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json()}
    project = make_project(owner, original_contract_value="2000000.00")
    client = owner.post("/api/v1/companies", json={"name": "Hill Country Health", "company_type": "owner"}).json()
    steel = owner.post("/api/v1/companies", json={"name": "Lone Star Steel", "company_type": "subcontractor"}).json()
    concrete = owner.post("/api/v1/companies", json={"name": "Austin Concrete", "company_type": "subcontractor"}).json()
    # approved budget so codes roll up
    b = owner.post(f"/api/v1/projects/{project['id']}/budgets", json={"name": "Original budget", "cost_code_set_id": s["id"]}).json()
    owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"cost_code_id": codes["03-100"], "description": "Footings", "amount": "250000.00"})
    owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "400000.00"})
    owner.post(f"/api/v1/budgets/{b['id']}/approve")
    return {"owner": owner, "set": s, "codes": codes, "project": project, "client": client, "steel": steel,
            "concrete": concrete}


def new_commitment(acct: Account, project_id: str, vendor_id: str, **kw):  # type: ignore[no-untyped-def]
    body = {"commitment_type": "subcontract", "vendor_company_id": vendor_id, "title": "Structural steel package",
            "contract_form": "aia_a401", "retention_percent": "10", "payment_terms_days": 30, **kw}
    resp = acct.post(f"/api/v1/projects/{project_id}/commitments", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- prime contracts -----------------------------------------------------------------------------------------------
def test_prime_contract_lifecycle(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project, codes = setup["owner"], setup["project"], setup["codes"]
    resp = owner.post(f"/api/v1/projects/{project['id']}/contracts", json={
        "title": "Construction agreement", "contract_form": "lump_sum", "client_company_id": setup["client"]["id"],
        "retention_percent": "5", "payment_terms_days": 30, "defects_period_months": 12,
        "liquidated_damages_amount": "2500.00", "liquidated_damages_period": "day", "bond_required": True,
        "bond_percent": "100", "start_date": "2026-01-05", "completion_date": "2027-03-31"})
    assert resp.status_code == 201, resp.text
    c = resp.json()
    assert c["number"] == "PC-001" and c["status"] == "draft" and c["currency"] == "USD"
    assert c["cost_code_set_id"] == setup["set"]["id"]  # defaulted from the approved budget
    assert c["client_company"]["name"] == "Hill Country Health"
    c = owner.post(f"/api/v1/contracts/{c['id']}/lines", json={"cost_code_id": codes["03-100"], "description": "Footings", "amount": "300000.00"}).json()
    c = owner.post(f"/api/v1/contracts/{c['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "450000.50"}).json()
    assert c["current_total"] == "750000.50" and c["original_sum"] is None
    stale = owner.post(f"/api/v1/contracts/{c['id']}/execute", json={"executed_date": TODAY, "version": 1})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_conflict"
    future = owner.post(f"/api/v1/contracts/{c['id']}/execute", json={"executed_date": (date.today() + timedelta(days=3)).isoformat(), "version": c["version"]})
    assert future.status_code == 422
    done = owner.post(f"/api/v1/contracts/{c['id']}/execute", json={"executed_date": TODAY, "version": c["version"]}).json()
    assert done["status"] == "executed" and done["original_sum"] == "750000.50" and done["is_editable"] is False
    # locked
    locked = owner.patch(f"/api/v1/contracts/{c['id']}", json={"version": done["version"], "retention_percent": "3"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "record_locked"
    assert owner.post(f"/api/v1/contracts/{c['id']}/lines", json={"description": "x", "amount": "1"}).status_code == 409
    assert owner.delete(f"/api/v1/contracts/{c['id']}").status_code == 409
    assert owner.post(f"/api/v1/contracts/{c['id']}/void", json={"version": done["version"]}).status_code == 409
    closed = owner.post(f"/api/v1/contracts/{c['id']}/close", json={"version": done["version"]}).json()
    assert closed["status"] == "closed" and closed["closed_at"]


def test_contract_validation(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project = setup["owner"], setup["project"]
    base = {"title": "Agreement", "contract_form": "lump_sum"}
    url = f"/api/v1/projects/{project['id']}/contracts"
    for bad in ({"contract_form": "jct_sbc"}, {"retention_percent": "101"}, {"liquidated_damages_amount": "100.00"},
                {"start_date": "2026-05-01", "completion_date": "2026-01-01"}, {"payment_terms_days": 400},
                {"client_company_id": setup["steel"]["id"].replace("-", "0", 1)[:36]}):
        assert owner.post(url, json={**base, **bad}).status_code == 422, bad
    owner.post(url, json={**base, "number": "PC-7"})
    assert owner.post(url, json={**base, "number": "pc-7"}).status_code == 409


def test_uk_contract_forms(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.post("/api/v1/auth/register", json={"full_name": "Alex QS", "email": "uk-contracts@example.com",
                                                      "password": "Correct-Horse-Battery-9", "organization_name": "Thames QS",
                                                      "country_code": "GB"})
    body = resp.json()
    client.cookies.clear()
    uk = Account(client, "uk-contracts@example.com", body["session"]["user"]["id"], body["session"]["memberships"][0]["tenant_id"], body["access_token"])
    vocab = uk.get("/api/v1/contracts/vocabulary").json()
    assert "nec4_ecc_c" in vocab["prime_forms"] and "nec4_ecs" in vocab["subcontract_forms"]
    assert "aia_a401" not in vocab["subcontract_forms"]
    p = make_project(uk, delivery_method="traditional", contract_type="jct_sbc")
    sub = uk.post("/api/v1/companies", json={"name": "Pennine Groundworks", "company_type": "subcontractor"}).json()
    assert uk.post(f"/api/v1/projects/{p['id']}/commitments", json={"commitment_type": "subcontract", "vendor_company_id": sub["id"],
                                                                    "title": "Groundworks", "contract_form": "aia_a401"}).status_code == 422
    sc = new_commitment(uk, p["id"], sub["id"], contract_form="jct_sbcsub", retention_percent="3")
    assert sc["currency"] == "GBP" and sc["number"] == "SC-001"


# --- commitments --------------------------------------------------------------------------------------------------
def test_commitment_lines_and_measured_pricing(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project, codes = setup["owner"], setup["project"], setup["codes"]
    sc = new_commitment(owner, project["id"], setup["steel"]["id"])
    url = f"/api/v1/commitments/{sc['id']}/lines"
    sc = owner.post(url, json={"cost_code_id": codes["05-100"], "description": "Fabricate and erect", "quantity": "142.5",
                               "unit": "ton", "unit_rate": "2950.333333"}).json()
    assert sc["lines"][0]["amount"] == "420422.50"  # 142.5 x 2950.333333 = 420422.4999... -> half-up
    sc = owner.post(url, json={"cost_code_id": codes["05-100"], "description": "Shop drawings", "amount": "12500.00"}).json()
    assert sc["current_total"] == "432922.50"
    for bad in ({"description": "x", "quantity": "1", "unit": "nr"},  # rate missing
                {"description": "x", "quantity": "1", "unit": "nr", "unit_rate": "5", "amount": "5"},
                {"description": "x"}, {"description": "x", "amount": 1.5},
                {"description": "x", "amount": "1", "cost_code_id": setup["client"]["id"]}):
        assert owner.post(url, json=bad).status_code == 422, bad
    po = new_commitment(owner, project["id"], setup["concrete"]["id"], commitment_type="purchase_order",
                        title="Ready-mix supply", contract_form="purchase_order")
    assert po["number"] == "PO-001"
    assert new_commitment(owner, project["id"], setup["steel"]["id"])["number"] == "SC-002"


def test_commitment_execute_freeze_and_db_guard(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project, codes = setup["owner"], setup["project"], setup["codes"]
    sc = new_commitment(owner, project["id"], setup["steel"]["id"])
    assert owner.post(f"/api/v1/commitments/{sc['id']}/execute", json={"executed_date": TODAY, "version": sc["version"]}).status_code == 422
    sc = owner.post(f"/api/v1/commitments/{sc['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "380000.00"}).json()
    sc = owner.post(f"/api/v1/commitments/{sc['id']}/execute", json={"executed_date": TODAY, "version": sc["version"]}).json()
    assert sc["status"] == "executed" and sc["original_sum"] == "380000.00"
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        for stmt in ("UPDATE commitment_lines SET amount = 1", "UPDATE commitments SET retention_percent = 0",
                     "DELETE FROM commitments WHERE status = 'executed'"):
            with pytest.raises(DBAPIError, match="cannot be"):
                conn.execute(text(stmt))
            conn.rollback()
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
    engine.dispose()


def test_void_and_delete_drafts(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project = setup["owner"], setup["project"]
    sc = new_commitment(owner, project["id"], setup["steel"]["id"])
    owner.post(f"/api/v1/commitments/{sc['id']}/lines", json={"description": "x", "amount": "10.00"})
    assert owner.delete(f"/api/v1/commitments/{sc['id']}").status_code == 204
    sc2 = new_commitment(owner, project["id"], setup["steel"]["id"])
    voided = owner.post(f"/api/v1/commitments/{sc2['id']}/void", json={"version": sc2["version"]}).json()
    assert voided["status"] == "void"
    assert owner.post(f"/api/v1/commitments/{sc2['id']}/close", json={"version": voided["version"]}).status_code == 409


def test_permissions_and_visibility(client, setup) -> None:  # type: ignore[no-untyped-def]
    owner, project = setup["owner"], setup["project"]
    sc = new_commitment(owner, project["id"], setup["steel"]["id"])
    owner.post(f"/api/v1/commitments/{sc['id']}/lines", json={"description": "x", "amount": "10.00"})
    pm = invite_and_join(owner, "project_manager")
    assert pm.get(f"/api/v1/commitments/{sc['id']}").status_code == 404  # not on the team
    owner.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    fresh = pm.get(f"/api/v1/commitments/{sc['id']}").json()
    assert fresh["can_execute"] is False and fresh["is_editable"] is True
    assert pm.post(f"/api/v1/commitments/{sc['id']}/execute", json={"executed_date": TODAY, "version": fresh["version"]}).status_code == 403
    field = invite_and_join(owner, "field_engineer")
    assert field.get("/api/v1/commitments").status_code == 403
    other = register(client, org="Rival Contractors")
    assert other.get(f"/api/v1/commitments/{sc['id']}").status_code == 404
    assert other.get("/api/v1/commitments").json() == []
    actions = [e["action"] for e in owner.get(f"/api/v1/audit-events?entity_id={sc['id']}").json()["items"]]
    assert "commitment.created" in actions and "commitment.line_added" in actions


# --- commercial summary ------------------------------------------------------------------------------------------
def test_commercial_summary_budget_vs_committed(setup) -> None:  # type: ignore[no-untyped-def]
    owner, project, codes = setup["owner"], setup["project"], setup["codes"]
    steel = new_commitment(owner, project["id"], setup["steel"]["id"])
    steel = owner.post(f"/api/v1/commitments/{steel['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "425000.00"}).json()
    owner.post(f"/api/v1/commitments/{steel['id']}/execute", json={"executed_date": TODAY, "version": steel["version"]})
    conc = new_commitment(owner, project["id"], setup["concrete"]["id"], title="Footings", contract_form="company_subcontract")
    owner.post(f"/api/v1/commitments/{conc['id']}/lines", json={"cost_code_id": codes["03-100"], "description": "Footings", "amount": "180000.00"})
    owner.post(f"/api/v1/commitments/{conc['id']}/lines", json={"description": "Uncoded extra", "amount": "5000.00"})
    s = owner.get(f"/api/v1/projects/{project['id']}/commercial-summary").json()
    rows = {r["code"]: r for r in s["rows"]}
    assert rows["05-100"]["budget"] == "400000.00" and rows["05-100"]["committed"] == "425000.00"
    assert rows["05-100"]["uncommitted"] == "-25000.00"
    assert rows["03-100"]["committed"] == "0.00" and rows["03-100"]["pending"] == "180000.00"
    assert rows[None]["pending"] == "5000.00"
    assert s["totals"]["budget"] == "650000.00" and s["totals"]["committed"] == "425000.00"
    assert s["totals"]["uncommitted"] == "225000.00"
    assert any("05-100" in w for w in s["warnings"])
    dash = owner.get("/api/v1/dashboard/summary").json()
    usd = next(r for r in dash["committed_cost"] if r["currency"] == "USD")
    assert usd["amount"] == "425000.00" and "Committed cost" not in dash["unavailable_metrics"]
