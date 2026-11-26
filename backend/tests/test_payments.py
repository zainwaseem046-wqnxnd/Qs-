"""Phase 3.1: payment applications (US) / interim valuations (UK)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import PASSWORD, Account, invite_and_join, make_project, register

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _execute(acct: Account, kind: str, rec: dict) -> dict:  # type: ignore[type-arg]
    resp = acct.post(f"/api/v1/{kind}/{rec['id']}/execute",
                     json={"executed_date": (TODAY - timedelta(days=60)).isoformat(), "version": rec["version"]})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _approved_change(acct: Account, contract_id: str, title: str, amount: str) -> dict:  # type: ignore[type-arg]
    co = acct.post("/api/v1/change-orders", json={"target_type": "contract", "target_id": contract_id,
                                                  "title": title}).json()
    co = acct.post(f"/api/v1/change-orders/{co['id']}/lines", json={"description": title, "amount": amount}).json()
    co = acct.post(f"/api/v1/change-orders/{co['id']}/submit", json={"version": co["version"]}).json()
    resp = acct.post(f"/api/v1/change-orders/{co['id']}/approve", json={"version": co["version"], "notes": "ok"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _contract(acct: Account, pid: str, *, retention: str = "5", days: int | None = 30, form: str = "lump_sum",
              lines: tuple[tuple[str, str], ...] = (("Substructure", "100000.00"), ("Frame", "50000.00"))) -> dict:  # type: ignore[type-arg]
    body = {"title": "Prime contract", "contract_form": form, "retention_percent": retention}
    if days is not None:
        body["payment_terms_days"] = days
    pc = acct.post(f"/api/v1/projects/{pid}/contracts", json=body).json()
    for d, a in lines:
        pc = acct.post(f"/api/v1/contracts/{pc['id']}/lines", json={"description": d, "amount": a}).json()
    return _execute(acct, "contracts", pc)


@pytest.fixture
def job(owner):  # type: ignore[no-untyped-def]
    project = make_project(owner)
    pc = _contract(owner, project["id"])
    _approved_change(owner, pc["id"], "Extra canopy", "12500.00")
    _approved_change(owner, pc["id"], "Omit paving", "-4000.00")
    return {"owner": owner, "pid": project["id"], "pc": pc}


def new_app(acct: Account, pid: str, contract_id: str, period_to: date = YESTERDAY, **kw):  # type: ignore[no-untyped-def]
    resp = acct.post(f"/api/v1/projects/{pid}/payment-applications",
                     json={"contract_id": contract_id, "period_to": period_to.isoformat(), **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


def put_line(acct: Account, app: dict, idx: int, **body):  # type: ignore[no-untyped-def,type-arg]
    return acct.put(f"/api/v1/payment-applications/{app['id']}/lines/{app['lines'][idx]['id']}", json=body)


def act(acct: Account, app: dict, action: str, **body):  # type: ignore[no-untyped-def,type-arg]
    return acct.post(f"/api/v1/payment-applications/{app['id']}/{action}", json={"version": app["version"], **body})


def test_full_cycle_with_certifier_cut_and_short_payment(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    a1 = new_app(owner, pid, pc["id"])
    assert a1["label"] == "Pay application 1" and a1["status"] == "draft"
    assert [ln["item"] for ln in a1["lines"]] == ["1", "2", "CO-001", "CO-002"]
    assert a1["retention_percent"] == "5.00" and a1["due_date"] == (TODAY + timedelta(days=30)).isoformat()
    assert a1["totals"]["contract_sum_to_date"] == "158500.00" and a1["totals"]["amount_due"] == "0.00"

    assert put_line(owner, a1, 0, percent_to_date="40").status_code == 200
    assert put_line(owner, a1, 1, materials_stored="7500.00").status_code == 200
    a1 = put_line(owner, a1, 3, this_period="-1000.00").json()
    t = a1["totals"]
    assert (t["completed_to_date"], t["retention"], t["amount_due"]) == ("46500.00", "2325.00", "44175.00")
    assert a1["lines"][0]["this_period"] == "40000.00" and a1["lines"][0]["percent_complete"] == "40.00"

    a1 = act(owner, a1, "submit").json()
    assert a1["status"] == "submitted" and a1["amount_due"] == "44175.00" and a1["is_editable"] is False
    assert put_line(owner, a1, 0, this_period="1.00").status_code == 409
    blocked = owner.post(f"/api/v1/projects/{pid}/payment-applications",
                         json={"contract_id": pc["id"], "period_to": TODAY.isoformat()})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "application_open"

    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert act(pm, a1, "certify").status_code == 403  # PMs prepare applications; certification is separate

    cut = act(owner, a1, "certify", certified_amount="40000.00")
    assert cut.status_code == 422 and cut.json()["error"]["details"][0]["field"] == "certification_note"
    assert act(owner, a1, "certify", certified_amount="50000.00", certification_note="x").status_code == 422
    a1 = act(owner, a1, "certify", certified_amount="40000.00", certification_note="Stored materials not verified").json()
    assert a1["status"] == "certified" and a1["outstanding"] == "40000.00"
    a1 = act(owner, a1, "payment", paid_amount="39000.00", payment_reference="BACS 7781").json()
    assert a1["status"] == "paid" and a1["outstanding"] == "1000.00"
    assert act(owner, a1, "payment").status_code == 409  # final

    a2 = new_app(owner, pid, pc["id"], period_to=TODAY)
    assert a2["number"] == 2 and a2["label"] == "Pay application 2"
    first = a2["lines"][0]
    assert (first["previous_work"], first["this_period"]) == ("40000.00", "0.00")
    assert a2["lines"][1]["materials_stored"] == "7500.00"  # stored balance carries forward until installed
    put_line(owner, a2, 0, this_period="10000.00")
    put_line(owner, a2, 1, this_period="7500.00", materials_stored="0.00")
    put_line(owner, a2, 2, percent_to_date="100")
    a2 = put_line(owner, a2, 3, this_period="-3000.00").json()
    assert a2["totals"]["previous_certified"] == "40000.00"
    assert a2["totals"]["amount_due"] == "22700.00"  # includes the 4,175.00 the certifier cut last time

    summary = owner.get(f"/api/v1/projects/{pid}/billing-summary").json()
    assert summary["certified_to_date"] == "40000.00" and summary["paid_to_date"] == "39000.00"
    assert summary["outstanding"] == "1000.00" and summary["retention_held"] == "2325.00"
    assert summary["billed_to_date"] == "46500.00" and summary["over_billed"] is None  # no approved forecast yet

    log = owner.get(f"/api/v1/audit-events?entity_type=payment_application&entity_id={a1['id']}").json()["items"]
    assert [e["action"] for e in log][:3] == ["payment_application.paid", "payment_application.certified",
                                              "payment_application.submitted"]


def test_database_freezes_submitted_and_paid_applications(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    a = new_app(owner, pid, pc["id"])
    a = put_line(owner, a, 0, this_period="1000.00").json()
    a = act(owner, a, "submit").json()
    engine = create_engine(get_settings().migration_database_url)  # even the schema owner
    with engine.connect() as conn:
        for stmt, msg in (
            (f"UPDATE payment_applications SET amount_due = 1 WHERE id = '{a['id']}'", "cannot be changed"),
            (f"UPDATE payment_application_lines SET this_period = 5 WHERE application_id = '{a['id']}'",
             "lines cannot be changed"),
            (f"UPDATE payment_applications SET status = 'paid' WHERE id = '{a['id']}'", "must be certified"),
            (f"DELETE FROM payment_applications WHERE id = '{a['id']}'", "only draft"),
        ):
            with pytest.raises(DBAPIError, match=msg):
                conn.execute(text(stmt))
            conn.rollback()
    a = act(owner, a, "certify").json()
    a = act(owner, a, "payment").json()
    assert a["paid_amount"] == a["certified_amount"] == "950.00"
    with engine.connect() as conn:
        with pytest.raises(DBAPIError, match="paid and cannot be changed"):
            conn.execute(text(f"UPDATE payment_applications SET notes = 'x' WHERE id = '{a['id']}'"))
        conn.rollback()
    engine.dispose()


def test_validation(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    draft_pc = owner.post(f"/api/v1/projects/{pid}/contracts", json={"title": "Unsigned", "contract_form": "lump_sum"}).json()
    r = owner.post(f"/api/v1/projects/{pid}/payment-applications", json={"contract_id": draft_pc["id"], "period_to": YESTERDAY.isoformat()})
    assert r.status_code == 409 and r.json()["error"]["code"] == "contract_not_executed"
    r = owner.post(f"/api/v1/projects/{pid}/payment-applications",
                   json={"contract_id": pc["id"], "period_to": YESTERDAY.isoformat(),
                         "application_date": (TODAY + timedelta(days=2)).isoformat()})
    assert r.status_code == 422
    a = new_app(owner, pid, pc["id"])
    over = put_line(owner, a, 0, this_period="100000.01")
    assert over.status_code == 422 and "exceed" in over.json()["error"]["message"]
    assert put_line(owner, a, 0, this_period="1.00", percent_to_date="10").status_code == 422
    assert put_line(owner, a, 0, this_period="1.005").status_code == 422  # more than 2 decimals
    assert put_line(owner, a, 0, this_period=1.5).status_code == 422  # floats rejected
    assert put_line(owner, a, 3, this_period="-5000.00").status_code == 422  # omission beyond its value
    assert put_line(owner, a, 3, materials_stored="10.00").status_code == 422
    bad = owner.patch(f"/api/v1/payment-applications/{a['id']}",
                      json={"version": a["version"], "due_date": TODAY.isoformat(),
                            "final_payment_date": YESTERDAY.isoformat()})
    assert bad.status_code == 422
    stale = owner.patch(f"/api/v1/payment-applications/{a['id']}", json={"version": a["version"] + 5, "notes": "x"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_conflict"
    ok = owner.patch(f"/api/v1/payment-applications/{a['id']}", json={"version": a["version"], "retention_percent": "2.5"})
    assert ok.status_code == 200 and ok.json()["retention_percent"] == "2.50"
    a = act(owner, ok.json(), "submit").json()
    a = act(owner, a, "certify").json()
    early = owner.post(f"/api/v1/projects/{pid}/payment-applications",
                       json={"contract_id": pc["id"], "period_to": (YESTERDAY - timedelta(days=1)).isoformat()})
    assert early.status_code == 422 and early.json()["error"]["details"][0]["field"] == "period_to"


def test_change_approved_during_draft_is_added_before_submission(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    a = new_app(owner, pid, pc["id"])
    _approved_change(owner, pc["id"], "Additional drainage", "8000.00")
    r = act(owner, a, "submit")
    assert r.status_code == 409 and r.json()["error"]["code"] == "schedule_changed"
    a = owner.get(f"/api/v1/payment-applications/{a['id']}").json()
    assert [ln["item"] for ln in a["lines"]][-1] == "CO-003"
    assert a["totals"]["contract_sum_to_date"] == "166500.00"
    assert act(owner, a, "submit").status_code == 200


def test_return_to_draft_and_delete(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    a = act(owner, new_app(owner, pid, pc["id"]), "submit").json()
    assert owner.delete(f"/api/v1/payment-applications/{a['id']}").status_code == 409
    a = act(owner, a, "return-to-draft").json()
    assert a["status"] == "draft" and a["is_editable"] is True
    assert owner.delete(f"/api/v1/payment-applications/{a['id']}").status_code == 204
    assert owner.get(f"/api/v1/projects/{pid}/payment-applications").json() == []


def test_permissions_and_isolation(client, job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    a = new_app(owner, pid, pc["id"])
    executive = invite_and_join(owner, "executive")
    assert executive.get(f"/api/v1/payment-applications/{a['id']}").status_code == 200
    assert put_line(executive, a, 0, this_period="1.00").status_code == 403
    viewer = invite_and_join(owner, "viewer")
    assert viewer.get(f"/api/v1/projects/{pid}/payment-applications").status_code in (403, 404)
    other = register(client, org="Rival GC")
    assert other.get(f"/api/v1/payment-applications/{a['id']}").status_code == 404
    assert other.post(f"/api/v1/projects/{pid}/payment-applications",
                      json={"contract_id": pc["id"], "period_to": YESTERDAY.isoformat()}).status_code == 404


def test_uk_valuation_dates_and_labels(client) -> None:  # type: ignore[no-untyped-def]
    email = "uk-pay@example.com"
    body = client.post("/api/v1/auth/register", json={"full_name": "Alex QS", "email": email, "password": PASSWORD,
                                                      "organization_name": "Thames QS", "country_code": "GB"}).json()
    client.cookies.clear()
    uk = Account(client, email, body["session"]["user"]["id"], body["session"]["memberships"][0]["tenant_id"],
                 body["access_token"])
    p = make_project(uk, delivery_method="traditional", contract_type="jct_sbc")
    jct = _contract(uk, p["id"], retention="3", days=14, form="jct_sbc")
    v = new_app(uk, p["id"], jct["id"], period_to=YESTERDAY)
    due = YESTERDAY + timedelta(days=7)
    assert v["label"] == "Valuation 1" and v["currency"] == "GBP" and v["retention_percent"] == "3.00"
    assert v["due_date"] == due.isoformat()
    assert v["final_payment_date"] == (due + timedelta(days=14)).isoformat()
    assert v["pay_less_notice_date"] == (due + timedelta(days=9)).isoformat()  # 5 days before the final date


def test_dashboard_outstanding_and_over_billing(job) -> None:  # type: ignore[no-untyped-def]
    owner, pid, pc = job["owner"], job["pid"], job["pc"]
    b = owner.post(f"/api/v1/projects/{pid}/budgets", json={"name": "Original budget"}).json()
    owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"description": "All", "amount": "120000.00"})
    owner.post(f"/api/v1/budgets/{b['id']}/approve")
    owner.post(f"/api/v1/projects/{pid}/cost-transactions",
               json={"transaction_date": TODAY.isoformat(), "description": "Costs", "amount": "30000.00"})
    f = owner.post(f"/api/v1/projects/{pid}/forecasts", json={"period": TODAY.replace(day=1).isoformat()}).json()
    f = owner.post(f"/api/v1/forecasts/{f['id']}/approve", json={"version": f["version"]}).json()
    # revenue 158,500 x 30,000 / 120,000 = 39,625.00 earned
    assert f["earned_revenue"] == "39625.00"
    a = new_app(owner, pid, pc["id"])
    a = put_line(owner, a, 0, this_period="50000.00").json()
    a = act(owner, a, "submit").json()
    pending = owner.get("/api/v1/dashboard/summary").json()["payments"][0]
    assert pending["awaiting_certification"] == "47500.00" and pending["outstanding"] == "0.00"
    assert (pending["over_billed"], pending["under_billed"], pending["projects_billed"]) == ("10375.00", "0.00", 1)
    act(owner, a, "certify")
    dash = owner.get("/api/v1/dashboard/summary").json()
    assert dash["payments"][0]["outstanding"] == "47500.00" and dash["payments"][0]["retention_held"] == "2500.00"
    assert dash["unavailable_metrics"] == ["Cash flow"]
    summary = owner.get(f"/api/v1/projects/{pid}/billing-summary").json()
    assert (summary["billed_to_date"], summary["earned_revenue"], summary["over_billed"]) == (
        "50000.00", "39625.00", "10375.00")
