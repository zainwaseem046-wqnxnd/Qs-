"""Phase 2.4: immutable cost ledger, CSV import, monthly forecasts, dashboard figures."""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import PASSWORD, Account, invite_and_join, make_project, register

TODAY = date.today()
CSV = "code,title,parent_code\n03,Concrete,\n03-100,Footings,03\n05,Metals,\n05-100,Structural steel,05\n"


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
    steel = owner.post("/api/v1/companies", json={"name": "Steel Co", "company_type": "subcontractor"}).json()
    pc = owner.post(f"/api/v1/projects/{project['id']}/contracts", json={"title": "Prime", "contract_form": "lump_sum"}).json()
    pc = owner.post(f"/api/v1/contracts/{pc['id']}/lines", json={"description": "Contract sum", "amount": "780000.00"}).json()
    owner.post(f"/api/v1/contracts/{pc['id']}/execute", json={"executed_date": TODAY.isoformat(), "version": pc["version"]})
    sc = owner.post(f"/api/v1/projects/{project['id']}/commitments", json={"commitment_type": "subcontract", "vendor_company_id": steel["id"], "title": "Steel", "contract_form": "aia_a401"}).json()
    sc = owner.post(f"/api/v1/commitments/{sc['id']}/lines", json={"cost_code_id": codes["05-100"], "description": "Steel", "amount": "425000.00"}).json()
    sc = owner.post(f"/api/v1/commitments/{sc['id']}/execute", json={"executed_date": TODAY.isoformat(), "version": sc["version"]}).json()
    return {"owner": owner, "codes": codes, "project": project, "sc": sc, "pid": project["id"]}


def post(acct: Account, pid: str, **kw):  # type: ignore[no-untyped-def]
    body = {"transaction_date": TODAY.isoformat(), "description": "Invoice", **kw}
    resp = acct.post(f"/api/v1/projects/{pid}/cost-transactions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def upload(acct: Account, pid: str, content: str, name: str = "costs.csv"):  # type: ignore[no-untyped-def]
    return acct.post(f"/api/v1/projects/{pid}/cost-transactions/import",
                     files={"file": (name, io.BytesIO(content.encode()), "text/csv")})


def test_post_reverse_and_ledger_immutability(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, codes, sc = job["owner"], job["pid"], job["codes"], job["sc"]
    tx = post(owner, pid, cost_code_id=codes["05-100"], commitment_id=sc["id"], amount="120000.00", reference="INV-1001")
    assert tx["vendor_name"] == "Steel Co" and tx["commitment_number"] == sc["number"]
    rev = owner.post(f"/api/v1/projects/{pid}/cost-transactions/{tx['id']}/reverse", json={"reason": "Posted to wrong job"})
    assert rev.status_code == 201 and rev.json()["amount"] == "-120000.00"
    again = owner.post(f"/api/v1/projects/{pid}/cost-transactions/{tx['id']}/reverse", json={"reason": "again"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_reversed"
    assert owner.post(f"/api/v1/projects/{pid}/cost-transactions/{rev.json()['id']}/reverse", json={"reason": "undo"}).status_code == 409
    page = owner.get(f"/api/v1/projects/{pid}/cost-transactions").json()
    assert page["total"] == 2 and page["amount_total"] == "0.00"
    assert next(t for t in page["items"] if t["id"] == tx["id"])["reversed"] is True
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        with pytest.raises(DBAPIError, match=r"permission denied|append-only"):
            conn.execute(text("UPDATE cost_transactions SET amount = 1"))
        conn.rollback()
    engine.dispose()
    owner_engine = create_engine(get_settings().migration_database_url)
    with owner_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("DELETE FROM cost_transactions"))
        conn.rollback()
    owner_engine.dispose()


def test_validation(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid = job["owner"], job["pid"]
    url = f"/api/v1/projects/{pid}/cost-transactions"
    base = {"transaction_date": TODAY.isoformat(), "description": "x"}
    for bad in ({"amount": "0"}, {"amount": 10.5}, {"amount": "1.234"},
                {"amount": "10", "transaction_date": (TODAY + timedelta(days=2)).isoformat()},
                {"amount": "10", "cost_code_id": job["sc"]["id"]}, {"amount": "10", "transaction_type": "budget"}):
        assert owner.post(url, json={**base, **bad}).status_code == 422, bad


def test_csv_import_all_or_nothing_and_duplicates(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, sc = job["owner"], job["pid"], job["sc"]
    bad = ("date,cost_code,description,amount,reference,type,commitment\n"
           "2026-01-15,05-100,Steel app 1,\"$95,000.00\",INV-1,actual,SC-001\n"
           "13/45/2026,99-999,Bad row,abc,,budget,SC-999\n")
    r = upload(owner, pid, bad).json()
    assert r["created"] == 0 and len(r["errors"]) >= 5
    assert owner.get(f"/api/v1/projects/{pid}/cost-transactions").json()["total"] == 0
    d1 = (TODAY - timedelta(days=40)).strftime("%m/%d/%Y")
    good = ("date,cost_code,description,amount,reference,type,commitment\n"
            f"{d1},05-100,Steel app 1,\"$95,000.00\",INV-1,actual,{sc['number']}\n"
            f"{TODAY.isoformat()},03-100,Concrete pour,\"12,345.67\",T-77,,\n"
            f"{TODAY.isoformat()},03-100,Credit note,(345.67),CN-1,,\n"
            f"{TODAY.isoformat()},,Site cleaning accrual,1500,,accrual,\n")
    r = upload(owner, pid, good).json()
    assert r == {"created": 4, "total": "108500.00", "errors": []}
    dup = upload(owner, pid, good, name="renamed.csv")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "duplicate_import"
    s = owner.get(f"/api/v1/projects/{pid}/commercial-summary").json()
    rows = {r["code"]: r for r in s["rows"]}
    assert rows["05-100"]["cost_to_date"] == "95000.00" and rows["03-100"]["cost_to_date"] == "12000.00"
    assert rows[None]["cost_to_date"] == "1500.00"


def test_uk_dates_in_import(client) -> None:  # type: ignore[no-untyped-def]
    body = client.post("/api/v1/auth/register", json={"full_name": "Alex QS", "email": "uk-costs@example.com", "password": PASSWORD,
                                                      "organization_name": "Thames QS", "country_code": "GB"}).json()
    client.cookies.clear()
    uk = Account(client, "uk-costs@example.com", body["session"]["user"]["id"], body["session"]["memberships"][0]["tenant_id"], body["access_token"])
    p = make_project(uk, delivery_method="traditional", contract_type="jct_sbc")
    d = (TODAY - timedelta(days=3))
    r = upload(uk, p["id"], f"date,cost_code,description,amount\n{d.strftime('%d/%m/%Y')},,Skip hire,£450.00\n").json()
    assert r["created"] == 1
    tx = uk.get(f"/api/v1/projects/{p['id']}/cost-transactions").json()["items"][0]
    assert tx["transaction_date"] == d.isoformat() and tx["amount"] == "450.00"


def test_forecast_lifecycle_and_figures(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, codes = job["owner"], job["pid"], job["codes"]
    post(owner, pid, cost_code_id=codes["05-100"], amount="340000.00")
    post(owner, pid, cost_code_id=codes["03-100"], amount="100000.00")
    post(owner, pid, amount="5000.00", transaction_type="accrual", description="Uncoded accrual")
    period = TODAY.replace(day=1).isoformat()
    assert owner.post(f"/api/v1/projects/{pid}/forecasts", json={"period": (TODAY.replace(day=1) + timedelta(days=40)).isoformat()}).status_code == 422
    f = owner.post(f"/api/v1/projects/{pid}/forecasts", json={"period": period})
    assert f.status_code == 201, f.text
    f = f.json()
    lines = {(ln["cost_code"] or {}).get("code"): ln for ln in f["lines"]}
    # greater_of default: steel committed 425,000 > budget 400,000 -> CTC 85,000
    assert lines["05-100"]["cost_to_complete"] == "85000.00" and lines["05-100"]["final_cost"] == "425000.00"
    assert lines["03-100"]["final_cost"] == "250000.00"
    assert lines[None]["final_cost"] == "5000.00"
    f = owner.put(f"/api/v1/forecasts/{f['id']}/lines/{lines[None]['id']}", json={"method": "manual", "manual_ctc": "0.00"}).json()
    assert owner.put(f"/api/v1/forecasts/{f['id']}/lines/{lines[None]['id']}", json={"method": "manual"}).status_code == 422
    f = owner.patch(f"/api/v1/forecasts/{f['id']}", json={"version": f["version"], "revenue_adjustment": "20000.00", "revenue_adjustment_note": "Probable approval of CO-004"}).json()
    assert f["revenue"] == "800000.00" and f["final_cost"] == "680000.00" and f["gross_profit"] == "120000.00"
    assert f["margin_percent"] == "15.00" and f["percent_complete"] == "65.44" and f["cost_to_date"] == "445000.00"
    assert owner.post(f"/api/v1/projects/{pid}/forecasts", json={"period": period}).status_code == 409
    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert pm.post(f"/api/v1/forecasts/{f['id']}/approve", json={"version": f["version"]}).status_code == 403
    approved = owner.post(f"/api/v1/forecasts/{f['id']}/approve", json={"version": f["version"]}).json()
    assert approved["status"] == "approved" and approved["final_cost"] == "680000.00"
    # later cost does not change the approved snapshot
    post(owner, pid, cost_code_id=codes["05-100"], amount="1000.00")
    assert owner.get(f"/api/v1/forecasts/{f['id']}").json()["cost_to_date"] == "445000.00"
    assert owner.patch(f"/api/v1/forecasts/{f['id']}", json={"version": approved["version"], "notes": "x"}).status_code == 409
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        with pytest.raises(DBAPIError, match="cannot be changed"):
            conn.execute(text("UPDATE forecast_lines SET final_cost = 1"))
        conn.rollback()
    engine.dispose()
    dash = owner.get("/api/v1/dashboard/summary").json()
    usd = next(x for x in dash["forecast"] if x["currency"] == "USD")
    assert usd["revenue"] == "800000.00" and usd["final_cost"] == "680000.00" and usd["margin_percent"] == "15.00"
    assert usd["cost_to_date"] == "445000.00" and usd["projects_forecast"] == 1
    assert "Forecast gross margin" not in dash["unavailable_metrics"]
    assert [x["period"] for x in owner.get(f"/api/v1/projects/{pid}/forecasts").json()] == [period]


def test_permissions_and_isolation(client, job) -> None:  # type: ignore[no-untyped-def]
    owner, pid = job["owner"], job["pid"]
    tx = post(owner, pid, amount="10.00")
    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert pm.get(f"/api/v1/projects/{pid}/cost-transactions").status_code == 200
    assert pm.post(f"/api/v1/projects/{pid}/cost-transactions", json={"transaction_date": TODAY.isoformat(), "description": "x", "amount": "1"}).status_code == 403
    viewer = invite_and_join(owner, "viewer")
    owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": viewer.user_id, "project_role": "viewer"})
    assert viewer.get(f"/api/v1/projects/{pid}/cost-transactions").status_code == 403
    other = register(client, org="Rival")
    assert other.get(f"/api/v1/projects/{pid}/cost-transactions").status_code == 404
    assert other.post(f"/api/v1/projects/{pid}/cost-transactions/{tx['id']}/reverse", json={"reason": "hack"}).status_code == 404
