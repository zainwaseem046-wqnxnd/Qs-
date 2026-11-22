"""Phase 2.3: change orders / variations / compensation events."""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import PASSWORD, Account, invite_and_join, make_project, register

TODAY = date.today().isoformat()
CSV = "code,title,parent_code\n03,Concrete,\n03-100,Footings,03\n05,Metals,\n05-100,Structural steel,05\n"


def _execute(acct: Account, kind: str, rec: dict) -> dict:  # type: ignore[type-arg]
    resp = acct.post(f"/api/v1/{kind}/{rec['id']}/execute", json={"executed_date": TODAY, "version": rec["version"]})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def job(owner):  # type: ignore[no-untyped-def]
    s = owner.post("/api/v1/cost-code-sets", json={"name": "Codes", "template_key": "masterformat_style"}).json()
    owner.post(f"/api/v1/cost-code-sets/{s['id']}/import", files={"file": ("c.csv", io.BytesIO(CSV.encode()), "text/csv")})
    codes = {c["code"]: c["id"] for c in owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json()}
    project = make_project(owner)
    b = owner.post(f"/api/v1/projects/{project['id']}/budgets", json={"name": "Original budget", "cost_code_set_id": s["id"]}).json()
    owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"cost_code_id": codes["03-100"], "description": "Footings", "amount": "250000.00"})
    owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "400000.00"})
    owner.post(f"/api/v1/budgets/{b['id']}/approve")
    client = owner.post("/api/v1/companies", json={"name": "Owner LLC", "company_type": "owner"}).json()
    steel = owner.post("/api/v1/companies", json={"name": "Steel Co", "company_type": "subcontractor"}).json()
    pc = owner.post(f"/api/v1/projects/{project['id']}/contracts", json={"title": "Prime", "contract_form": "lump_sum", "client_company_id": client["id"]}).json()
    pc = owner.post(f"/api/v1/contracts/{pc['id']}/lines", json={"cost_code_id": codes["03-100"], "description": "Footings", "amount": "300000.00"}).json()
    pc = owner.post(f"/api/v1/contracts/{pc['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "480000.00"}).json()
    pc = _execute(owner, "contracts", pc)
    sc = owner.post(f"/api/v1/projects/{project['id']}/commitments", json={"commitment_type": "subcontract", "vendor_company_id": steel["id"], "title": "Steel", "contract_form": "aia_a401"}).json()
    sc = owner.post(f"/api/v1/commitments/{sc['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "390000.00"}).json()
    sc = _execute(owner, "commitments", sc)
    return {"owner": owner, "codes": codes, "project": project, "pc": pc, "sc": sc, "steel": steel}


def raise_co(acct: Account, target_type: str, target_id: str, **kw):  # type: ignore[no-untyped-def]
    resp = acct.post("/api/v1/change-orders", json={"target_type": target_type, "target_id": target_id,
                                                    "title": kw.pop("title", "Added canopy"), **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


def act(acct: Account, co: dict, action: str, **body):  # type: ignore[no-untyped-def,type-arg]
    return acct.post(f"/api/v1/change-orders/{co['id']}/{action}", json={"version": co["version"], **body})


def test_client_change_lifecycle_and_revised_sum(job) -> None:  # type: ignore[no-untyped-def]
    owner, codes, pc = job["owner"], job["codes"], job["pc"]
    co = raise_co(owner, "contract", pc["id"], reason="client_instruction", reference="CI-014",
                  schedule_impact_days=10, notified_date=TODAY)
    assert co["number"] == "CO-001" and co["label"] == "Change order" and co["status"] == "draft"
    assert co["target"]["number"] == pc["number"] and co["target"]["counterparty"] == "Owner LLC"
    assert act(owner, co, "submit").json()["error"]["code"] == "validation_failed"  # no lines
    co = owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={
        "cost_code_id": codes["05-100"], "description": "Canopy steel", "quantity": "4.5", "unit": "ton",
        "unit_rate": "3250.00", "budget_amount": "12000.00"}).json()
    co = owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={
        "cost_code_id": codes["03-100"], "description": "Omit pile cap P4", "amount": "-2500.00",
        "budget_amount": "-1800.00"}).json()
    assert co["total"] == "12125.00" and co["budget_total"] == "10200.00"  # 14,625.00 - 2,500.00
    co = act(owner, co, "submit").json()
    assert co["status"] == "submitted"
    # content frozen while submitted
    assert owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={"description": "x", "amount": "1"}).status_code == 409
    assert owner.patch(f"/api/v1/change-orders/{co['id']}", json={"version": co["version"], "title": "New"}).status_code == 409
    co = act(owner, co, "approve", notes="Agreed at progress meeting 7").json()
    assert co["status"] == "approved" and co["decision_notes"] == "Agreed at progress meeting 7"
    assert act(owner, co, "withdraw").status_code == 409  # final
    contract = owner.get(f"/api/v1/contracts/{pc['id']}").json()
    assert contract["original_sum"] == "780000.00"  # untouched
    assert contract["approved_changes"] == "12125.00" and contract["revised_sum"] == "792125.00"
    listing = owner.get(f"/api/v1/contracts?project_id={job['project']['id']}").json()
    assert listing[0]["revised_sum"] == "792125.00"


def test_negotiation_reject_withdraw_and_pending(job) -> None:  # type: ignore[no-untyped-def]
    owner, pc = job["owner"], job["pc"]
    co = raise_co(owner, "contract", pc["id"])
    co = owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={"description": "Canopy", "amount": "15000.00"}).json()
    co = act(owner, co, "submit").json()
    assert owner.get(f"/api/v1/contracts/{pc['id']}").json()["pending_changes"] == "15000.00"
    co = act(owner, co, "return-to-draft").json()
    line = co["lines"][0]["id"]
    co = owner.put(f"/api/v1/change-orders/{co['id']}/lines/{line}", json={"description": "Canopy (negotiated)", "amount": "13500.00"}).json()
    co = act(owner, co, "submit").json()
    assert act(owner, co, "reject").status_code == 422  # reason required
    co = act(owner, co, "reject", notes="Within original scope per spec 05 12 00").json()
    assert co["status"] == "rejected"
    c = owner.get(f"/api/v1/contracts/{pc['id']}").json()
    assert c["approved_changes"] == "0.00" and c["pending_changes"] == "0.00"
    co2 = raise_co(owner, "contract", pc["id"], title="Extra paving")
    assert co2["number"] == "CO-002"
    co2 = act(owner, co2, "withdraw").json()
    assert co2["status"] == "withdrawn"
    co3 = raise_co(owner, "contract", pc["id"], title="Draft to delete")
    assert owner.delete(f"/api/v1/change-orders/{co3['id']}").status_code == 204


def test_commitment_change_and_cost_summary(job) -> None:  # type: ignore[no-untyped-def]
    owner, codes, pc, sc, project = job["owner"], job["codes"], job["pc"], job["sc"], job["project"]
    sco = raise_co(owner, "commitment", sc["id"], title="Canopy steel")
    assert sco["number"] == "SCO-001" and sco["label"] == "Subcontract change order"
    bad = owner.post(f"/api/v1/change-orders/{sco['id']}/lines", json={"description": "x", "amount": "1", "budget_amount": "1"})
    assert bad.status_code == 422  # budget adjustments only on client-side changes
    sco = owner.post(f"/api/v1/change-orders/{sco['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Canopy", "amount": "11000.00"}).json()
    # pending before approval
    s = owner.get(f"/api/v1/projects/{project['id']}/commercial-summary").json()
    steel = next(r for r in s["rows"] if r["code"] == "05-100")
    assert steel["committed"] == "390000.00" and steel["pending"] == "11000.00"
    sco = act(owner, act(owner, sco, "submit").json(), "approve").json()
    assert sco["status"] == "approved"
    co = raise_co(owner, "contract", pc["id"])
    co = owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Canopy", "amount": "14625.00", "budget_amount": "12000.00"}).json()
    act(owner, act(owner, co, "submit").json(), "approve")
    s = owner.get(f"/api/v1/projects/{project['id']}/commercial-summary").json()
    steel = next(r for r in s["rows"] if r["code"] == "05-100")
    assert steel["budget"] == "400000.00" and steel["budget_changes"] == "12000.00"
    assert steel["revised_budget"] == "412000.00"
    assert steel["committed"] == "401000.00" and steel["pending"] == "0.00"
    assert steel["uncommitted"] == "11000.00"
    assert steel["contract_value"] == "494625.00"
    assert s["totals"]["revised_budget"] == "662000.00"
    assert owner.get(f"/api/v1/commitments/{sc['id']}").json()["revised_sum"] == "401000.00"


def test_target_must_be_executed_and_db_freeze(job) -> None:  # type: ignore[no-untyped-def]
    owner, project, steel = job["owner"], job["project"], job["steel"]
    draft_sc = owner.post(f"/api/v1/projects/{project['id']}/commitments", json={"commitment_type": "purchase_order", "vendor_company_id": steel["id"], "title": "Bolts", "contract_form": "purchase_order"}).json()
    resp = owner.post("/api/v1/change-orders", json={"target_type": "commitment", "target_id": draft_sc["id"], "title": "x2"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "target_not_executed"
    co = raise_co(owner, "contract", job["pc"]["id"])
    co = owner.post(f"/api/v1/change-orders/{co['id']}/lines", json={"description": "x", "amount": "100.00"}).json()
    act(owner, act(owner, co, "submit").json(), "approve")
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        for stmt in ("UPDATE change_order_lines SET amount = 1", "UPDATE change_orders SET title = 'x'",
                     "DELETE FROM change_orders WHERE status = 'approved'"):
            with pytest.raises(DBAPIError, match="cannot be changed"):
                conn.execute(text(stmt))
            conn.rollback()
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
    engine.dispose()


def test_validation_overdue_and_dashboard(job) -> None:  # type: ignore[no-untyped-def]
    owner, pc = job["owner"], job["pc"]
    base = {"target_type": "contract", "target_id": pc["id"], "title": "Valid title"}
    for bad in ({"reason": "whim"}, {"notified_date": TODAY, "response_due_date": "2000-01-01"},
                {"schedule_impact_days": 99999}):
        assert owner.post("/api/v1/change-orders", json={**base, **bad}).status_code == 422, bad
    past = (date.today() - timedelta(days=3)).isoformat()
    co = raise_co(owner, "contract", pc["id"], notified_date=(date.today() - timedelta(days=30)).isoformat(), response_due_date=past)
    url = f"/api/v1/change-orders/{co['id']}/lines"
    for bad in ({"description": "x", "quantity": "1", "unit": "nr"}, {"description": "x"},
                {"description": "x", "amount": 1.25}, {"description": "x", "quantity": "-2", "unit": "nr", "unit_rate": "-5"}):
        assert owner.post(url, json=bad).status_code == 422, bad
    co = owner.post(url, json={"description": "Omit", "quantity": "-2", "unit": "nr", "unit_rate": "1250.005"}).json()
    assert co["total"] == "-2500.01" and co["overdue"] is True
    co = act(owner, co, "submit").json()
    dash = owner.get("/api/v1/dashboard/summary").json()
    pending = next(p for p in dash["pending_changes"] if p["currency"] == "USD")
    assert pending == {"currency": "USD", "amount": "-2500.01", "count": 1, "overdue_count": 1}
    assert "Pending changes" not in dash["unavailable_metrics"] and "Revised budget" not in dash["unavailable_metrics"]


def test_permissions_isolation_and_audit(client, job) -> None:  # type: ignore[no-untyped-def]
    owner, project, pc = job["owner"], job["project"], job["pc"]
    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    co = raise_co(pm, "contract", pc["id"])
    co = pm.post(f"/api/v1/change-orders/{co['id']}/lines", json={"description": "x", "amount": "500.00"}).json()
    co = act(pm, co, "submit").json()
    assert co["can_approve"] is False
    assert act(pm, co, "approve").status_code == 403
    viewer = invite_and_join(owner, "viewer")
    assert viewer.get("/api/v1/change-orders").status_code == 403
    other = register(client, org="Rival GC")
    assert other.get(f"/api/v1/change-orders/{co['id']}").status_code == 404
    assert other.post("/api/v1/change-orders", json={"target_type": "contract", "target_id": pc["id"], "title": "Hijack"}).status_code == 422
    actions = [e["action"] for e in owner.get(f"/api/v1/audit-events?entity_id={co['id']}").json()["items"]]
    assert actions[:3] == ["change_order.submitted", "change_order.line_added", "change_order.created"]


def test_uk_variation_and_compensation_event_labels(client) -> None:  # type: ignore[no-untyped-def]
    email = "uk-co@example.com"
    body = client.post("/api/v1/auth/register", json={"full_name": "Alex QS", "email": email, "password": PASSWORD,
                                                      "organization_name": "Thames QS", "country_code": "GB"}).json()
    client.cookies.clear()
    uk = Account(client, email, body["session"]["user"]["id"], body["session"]["memberships"][0]["tenant_id"], body["access_token"])
    p = make_project(uk, delivery_method="traditional", contract_type="jct_sbc")
    sub = uk.post("/api/v1/companies", json={"name": "Pennine Ltd", "company_type": "subcontractor"}).json()
    jct = uk.post(f"/api/v1/projects/{p['id']}/contracts", json={"title": "Main contract", "contract_form": "jct_sbc"}).json()
    jct = _execute(uk, "contracts", uk.post(f"/api/v1/contracts/{jct['id']}/lines", json={"description": "Works", "amount": "1000000.00"}).json())
    nec_sub = uk.post(f"/api/v1/projects/{p['id']}/commitments", json={"commitment_type": "subcontract", "vendor_company_id": sub["id"], "title": "Groundworks", "contract_form": "nec4_ecs"}).json()
    nec_sub = _execute(uk, "commitments", uk.post(f"/api/v1/commitments/{nec_sub['id']}/lines", json={"description": "Works", "amount": "250000.00"}).json())
    var = raise_co(uk, "contract", jct["id"], title="Additional drainage")
    assert (var["label"], var["number"], var["currency"]) == ("Variation", "VAR-001", "GBP")
    ce = raise_co(uk, "commitment", nec_sub["id"], title="Unforeseen obstruction", reason="unforeseen_conditions")
    assert (ce["label"], ce["number"]) == ("Compensation event", "SCE-001")
