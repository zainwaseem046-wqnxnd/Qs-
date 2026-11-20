"""Phase 2.1: customer-defined cost codes, versioned estimates, budgets."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import Account, invite_and_join, make_project, register


def make_set(acct: Account, template: str = "nrm1_elemental", name: str = "Company elemental codes") -> dict:
    resp = acct.post("/api/v1/cost-code-sets", json={"name": name, "template_key": template})
    assert resp.status_code == 201, resp.text
    return resp.json()


def import_codes(acct: Account, set_id: str, csv_text: str):  # type: ignore[no-untyped-def]
    return acct.post(f"/api/v1/cost-code-sets/{set_id}/import",
                     files={"file": ("codes.csv", io.BytesIO(csv_text.encode()), "text/csv")})


CODES_CSV = """code,title,parent_code,unit
2,Superstructure,,
2.1,Frame,2,
2.1.1,Concrete frame,2.1,m3
1,Substructure,,
1.1,Foundations,1,
1.1.1,Pad foundations,1.1,m3
"""


# --- cost codes -------------------------------------------------------------------------------------------
def test_templates_provide_level_names_only(owner) -> None:  # type: ignore[no-untyped-def]
    templates = {t["key"]: t for t in owner.get("/api/v1/cost-code-sets/templates").json()}
    assert templates["nrm1_elemental"]["level_names"] == ["Group element", "Element", "Sub-element", "Component"]
    s = make_set(owner)
    assert s["level_names"][0] == "Group element" and s["code_count"] == 0
    custom = owner.post("/api/v1/cost-code-sets", json={"name": "Ours", "template_key": "custom"})
    assert custom.status_code == 422
    ok = owner.post("/api/v1/cost-code-sets", json={"name": "Ours", "template_key": "custom",
                                                     "level_names": ["Package", "Item"]})
    assert ok.status_code == 201 and ok.json()["level_names"] == ["Package", "Item"]
    dup = owner.post("/api/v1/cost-code-sets", json={"name": "OURS", "template_key": "trade_packages"})
    assert dup.status_code == 409


def test_csv_import_resolves_parents_in_any_order(owner) -> None:  # type: ignore[no-untyped-def]
    s = make_set(owner)
    resp = import_codes(owner, s["id"], CODES_CSV)
    assert resp.json() == {"created": 6, "errors": []}
    codes = {c["code"]: c for c in owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json()}
    assert codes["2.1.1"]["level"] == 3 and codes["2.1.1"]["unit"] == "m3"
    assert codes["2.1.1"]["parent_id"] == codes["2.1"]["id"]
    assert [c["code"] for c in owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes?q=frame").json()] == ["2.1", "2.1.1"]


def test_csv_import_is_all_or_nothing_with_row_errors(owner) -> None:  # type: ignore[no-untyped-def]
    s = owner.post("/api/v1/cost-code-sets", json={"name": "Two level", "template_key": "nrm2_work_sections"}).json()
    bad = "code,title,parent_code\nA,Groundworks,\nA.1,Excavation,A\nA.1.1,Too deep,A.1\nB.1,Orphan,B\nA,Duplicate,\n,No code,\n"
    result = import_codes(owner, s["id"], bad).json()
    assert result["created"] == 0
    messages = " | ".join(e["message"] for e in result["errors"])
    assert "level 3" in messages and "Parent code 'B' not found" in messages
    assert "Duplicate code A" in messages and "Invalid code" in messages
    assert owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json() == []
    no_header = import_codes(owner, s["id"], "foo,bar\n1,2\n")
    assert no_header.status_code == 422


def test_code_crud_depth_and_in_use_protection(owner) -> None:  # type: ignore[no-untyped-def]
    s = owner.post("/api/v1/cost-code-sets", json={"name": "Flat", "template_key": "custom", "level_names": ["Code"]}).json()
    top = owner.post(f"/api/v1/cost-code-sets/{s['id']}/codes", json={"code": "100", "title": "Prelims"}).json()
    child = owner.post(f"/api/v1/cost-code-sets/{s['id']}/codes",
                       json={"code": "100.1", "title": "Too deep", "parent_id": top["id"]})
    assert child.status_code == 422
    assert owner.post(f"/api/v1/cost-code-sets/{s['id']}/codes", json={"code": "100", "title": "x"}).status_code == 409
    assert owner.post(f"/api/v1/cost-code-sets/{s['id']}/codes", json={"code": "bad code!", "title": "x"}).status_code == 422
    # use it on an estimate line, then delete must be refused and deactivation allowed
    project = make_project(owner)
    est = owner.post(f"/api/v1/projects/{project['id']}/estimates", json={"name": "Estimate A", "cost_code_set_id": s["id"]}).json()
    owner.post(f"/api/v1/estimates/{est['id']}/versions/1/lines",
               json={"cost_code_id": top["id"], "description": "Site set-up", "quantity": "1", "unit": "item",
                     "other_rate": "5000"})
    resp = owner.delete(f"/api/v1/cost-code-sets/{s['id']}/codes/{top['id']}")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "cost_code_in_use"
    off = owner.patch(f"/api/v1/cost-code-sets/{s['id']}/codes/{top['id']}", json={"is_active": False})
    assert off.json()["is_active"] is False
    assert owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json() == []


def test_cost_code_permissions_and_isolation(client, owner) -> None:  # type: ignore[no-untyped-def]
    s = make_set(owner)
    pm = invite_and_join(owner, "project_manager")
    assert pm.get("/api/v1/cost-code-sets").status_code == 200
    assert pm.post("/api/v1/cost-code-sets", json={"name": "PM set", "template_key": "trade_packages"}).status_code == 403
    viewer = invite_and_join(owner, "viewer")
    assert viewer.get("/api/v1/cost-code-sets").status_code == 403
    other = register(client, org="Other Org")
    assert other.get(f"/api/v1/cost-code-sets/{s['id']}").status_code == 404
    assert other.get("/api/v1/cost-code-sets").json() == []


# --- estimates ---------------------------------------------------------------------------------------------
@pytest.fixture
def priced_estimate(owner):  # type: ignore[no-untyped-def]
    s = make_set(owner)
    import_codes(owner, s["id"], CODES_CSV)
    codes = {c["code"]: c["id"] for c in owner.get(f"/api/v1/cost-code-sets/{s['id']}/codes").json()}
    project = make_project(owner)
    est = owner.post(f"/api/v1/projects/{project['id']}/estimates",
                     json={"name": "Stage 3 cost plan", "estimate_type": "cost_plan", "cost_code_set_id": s["id"],
                           "price_base_date": "2026-10-01"})
    assert est.status_code == 201, est.text
    est = est.json()
    base = f"/api/v1/estimates/{est['id']}/versions/1"
    owner.post(f"{base}/lines", json={"cost_code_id": codes["2.1.1"], "description": "RC frame", "quantity": "125.5",
                                      "unit": "m3", "labour_hours_per_unit": "0.85", "labour_rate": "62.40",
                                      "material_rate": "148.00", "material_waste_percent": "5",
                                      "equipment_rate": "18.25"})
    owner.post(f"{base}/lines", json={"cost_code_id": codes["1.1.1"], "description": "Pad foundations",
                                      "quantity": "10", "unit": "m3", "subcontract_rate": "1000.005"})
    owner.post(f"{base}/lines", json={"description": "Provisional sum — utilities diversion", "line_type": "provisional_sum",
                                      "quantity": "1", "unit": "sum", "other_rate": "25000"})
    owner.post(f"{base}/lines", json={"description": "Upgraded cladding", "inclusion": "alternate",
                                      "alternate_label": "Alt 1 — cladding", "quantity": "2", "unit": "item",
                                      "material_rate": "500"})
    resp = owner.put(f"{base}/markups", json={"markups": [
        {"name": "Preliminaries", "percent": "12.5", "basis": "direct_cost"},
        {"name": "Contingency", "percent": "5", "basis": "cumulative"},
        {"name": "Overheads & profit", "percent": "7.25", "basis": "cumulative", "include_in_budget": False},
    ]})
    assert resp.status_code == 200, resp.text
    return {"owner": owner, "project": project, "estimate": est, "codes": codes, "set": s, "base": base}


def test_estimate_totals_are_exact(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base = priced_estimate["owner"], priced_estimate["base"]
    v = owner.get(base).json()
    frame = next(line for line in v["lines"] if line["description"] == "RC frame")
    assert frame["calc"]["total"] == "28449.60" and frame["calc"]["labour_unit"] == "53.040000"
    t = v["totals"]
    # direct = 28,449.60 + 10,000.05 + 25,000.00 = 63,449.65
    assert t["direct_cost"] == "63449.65"
    # prelims 12.5% = 7,931.21 (7,931.20625); contingency 5% of 71,380.86 = 3,569.04 (3,569.043);
    # OH&P 7.25% of 74,949.90 = 5,433.87 (5,433.867...)
    assert [m["amount"] for m in v["markups"]] == ["7931.21", "3569.04", "5433.87"]
    assert t["markup_total"] == "16934.12" and t["total"] == "80383.77"
    assert t["alternates"] == [{"label": "Alt 1 — cladding", "amount": "1000.00"}]
    assert v["status"] == "draft" and v["is_editable"] is True


def test_calculate_line_preview_matches_saved_line(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner = priced_estimate["owner"]
    preview = owner.post("/api/v1/estimating/calculate-line", json={
        "quantity": "125.5", "labour_hours_per_unit": "0.85", "labour_rate": "62.40", "material_rate": "148.00",
        "material_waste_percent": "5", "equipment_rate": "18.25"}).json()
    assert preview["total"] == "28449.60" and preview["equipment_total"] == "2290.38"
    assert owner.post("/api/v1/estimating/calculate-line", json={"quantity": 1.5}).status_code == 422


def test_line_validation(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base = priced_estimate["owner"], priced_estimate["base"]
    good = {"description": "x", "quantity": "1", "unit": "m2"}
    for bad in ({"quantity": "-1"}, {"quantity": "1.12345"}, {"labour_rate": "1.1234567"},
                {"material_waste_percent": "101"}, {"inclusion": "alternate"}, {"quantity": 2.5}, {"unit": ""}):
        assert owner.post(f"{base}/lines", json={**good, **bad}).status_code == 422, bad
    other_set = owner.post("/api/v1/cost-code-sets", json={"name": "Else", "template_key": "trade_packages"}).json()
    foreign = owner.post(f"/api/v1/cost-code-sets/{other_set['id']}/codes", json={"code": "Z", "title": "Z"}).json()
    resp = owner.post(f"{base}/lines", json={**good, "cost_code_id": foreign["id"]})
    assert resp.status_code == 422 and resp.json()["error"]["details"][0]["field"] == "cost_code_id"


def test_issue_freezes_version_and_new_version_copies(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base, est = priced_estimate["owner"], priced_estimate["base"], priced_estimate["estimate"]
    issued = owner.post(f"{base}/issue").json()
    assert issued["status"] == "issued" and issued["total"] == "80383.77" and issued["is_editable"] is False
    line_id = issued["lines"][0]["id"]
    locked = owner.post(f"{base}/lines", json={"description": "late", "quantity": "1", "unit": "nr"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "version_locked"
    assert owner.delete(f"{base}/lines/{line_id}").status_code == 409
    assert owner.put(f"{base}/markups", json={"markups": []}).status_code == 409

    v2 = owner.post(f"/api/v1/estimates/{est['id']}/versions")
    assert v2.status_code == 201 and v2.json()["version_number"] == 2 and v2.json()["status"] == "draft"
    assert v2.json()["totals"]["total"] == "80383.77"
    assert owner.post(f"/api/v1/estimates/{est['id']}/versions").json()["error"]["code"] == "draft_exists"
    v2_line = next(line for line in v2.json()["lines"] if line["description"] == "Pad foundations")
    owner.put(f"/api/v1/estimates/{est['id']}/versions/2/lines/{v2_line['id']}",
              json={"description": "Pad foundations", "quantity": "12", "unit": "m3", "subcontract_rate": "1000.005",
                    "cost_code_id": v2_line["cost_code"]["id"]})
    cmp = owner.get(f"/api/v1/estimates/{est['id']}/compare?from_version=1&to_version=2").json()
    pad = next(r for r in cmp["rows"] if r["cost_code"] == "1.1.1")
    assert (pad["from_amount"], pad["to_amount"], pad["change"]) == ("10000.05", "12000.06", "2000.01")
    # v1 is untouched
    assert owner.get(base).json()["totals"]["total"] == "80383.77"


def test_database_blocks_changes_to_issued_versions(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base = priced_estimate["owner"], priced_estimate["base"]
    owner.post(f"{base}/issue")
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        for stmt in ("UPDATE estimate_lines SET quantity = 999", "UPDATE estimate_versions SET total = 1",
                     "DELETE FROM estimate_markups"):
            with pytest.raises(DBAPIError, match="cannot be changed"):
                conn.execute(text(stmt))
            conn.rollback()
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
    engine.dispose()


def test_approval_permissions(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base = priced_estimate["owner"], priced_estimate["base"]
    project = priced_estimate["project"]
    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert pm.post(f"{base}/approve").status_code == 403  # permission is checked before status
    assert pm.post(f"{base}/issue").status_code == 200   # PMs may issue
    assert pm.post(f"{base}/approve").status_code == 403  # but not approve
    cm = invite_and_join(owner, "commercial_manager")
    approved = cm.post(f"{base}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    actions = [e["action"] for e in owner.get(f"/api/v1/audit-events?entity_id={priced_estimate['estimate']['id']}&limit=100").json()["items"]]
    assert {"estimate.version_approved", "estimate.version_issued", "estimate.markups_updated", "estimate.line_added"} <= set(actions)


def test_estimate_visibility_and_isolation(client, priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, est = priced_estimate["owner"], priced_estimate["estimate"]
    field = invite_and_join(owner, "field_engineer")
    assert field.get(f"/api/v1/estimates/{est['id']}").status_code == 403
    pm = invite_and_join(owner, "project_manager")  # not on the project team
    assert pm.get(f"/api/v1/estimates/{est['id']}").status_code == 404
    assert pm.get("/api/v1/estimates").json() == []
    other = register(client, org="Rival Builders")
    assert other.get(f"/api/v1/estimates/{est['id']}").status_code == 404


def test_archived_project_estimates_read_only(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base, project = priced_estimate["owner"], priced_estimate["base"], priced_estimate["project"]
    owner.post(f"/api/v1/projects/{project['id']}/archive")
    resp = owner.post(f"{base}/lines", json={"description": "x", "quantity": "1", "unit": "nr"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "project_archived"


# --- budgets --------------------------------------------------------------------------------------------------
def _approve(owner: Account, base: str) -> None:
    owner.post(f"{base}/issue")
    owner.post(f"{base}/approve")


def test_budget_from_approved_estimate(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, base, project, est = (priced_estimate[k] for k in ("owner", "base", "project", "estimate"))
    early = owner.post(f"/api/v1/projects/{project['id']}/budgets/from-estimate",
                       json={"estimate_id": est["id"], "version_number": 1})
    assert early.status_code == 409 and early.json()["error"]["code"] == "estimate_not_approved"
    _approve(owner, base)
    resp = owner.post(f"/api/v1/projects/{project['id']}/budgets/from-estimate",
                      json={"estimate_id": est["id"], "version_number": 1})
    assert resp.status_code == 201, resp.text
    b = resp.json()
    lines = [(ln["cost_code"]["code"] if ln["cost_code"] else None, ln["description"], ln["amount"]) for ln in b["lines"]]
    assert lines == [
        ("1.1.1", "Pad foundations", "10000.05"),
        ("2.1.1", "Concrete frame", "28449.60"),
        (None, "Unassigned (no cost code)", "25000.00"),
        (None, "Markup: Preliminaries", "7931.21"),
        (None, "Markup: Contingency", "3569.04"),
    ]
    # Budget = estimate total (80,383.77) - OH&P not budgeted (5,433.87); alternates excluded
    assert b["total"] == "74949.90"
    assert b["status"] == "draft" and b["source_description"] == "Stage 3 cost plan — version 1"


def test_budget_edit_approve_and_freeze(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, project, codes = priced_estimate["owner"], priced_estimate["project"], priced_estimate["codes"]
    b = owner.post(f"/api/v1/projects/{project['id']}/budgets",
                   json={"name": "Original budget", "cost_code_set_id": priced_estimate["set"]["id"]}).json()
    assert owner.post(f"/api/v1/budgets/{b['id']}/approve").status_code == 422  # no lines
    b = owner.post(f"/api/v1/budgets/{b['id']}/lines",
                   json={"cost_code_id": codes["2.1"], "description": "Frame", "amount": "100000.10"}).json()
    b = owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"description": "Contingency", "amount": "5000"}).json()
    assert b["total"] == "105000.10"
    assert owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"description": "x", "amount": 1.5}).status_code == 422
    line_id = b["lines"][1]["id"]
    b = owner.put(f"/api/v1/budgets/{b['id']}/lines/{line_id}", json={"description": "Contingency", "amount": "4999.90"}).json()
    assert b["total"] == "105000.00"

    pm = invite_and_join(owner, "project_manager")
    owner.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert pm.post(f"/api/v1/budgets/{b['id']}/approve").status_code == 403
    approved = owner.post(f"/api/v1/budgets/{b['id']}/approve").json()
    assert approved["status"] == "approved" and approved["total"] == "105000.00" and approved["is_editable"] is False
    locked = owner.post(f"/api/v1/budgets/{b['id']}/lines", json={"description": "late", "amount": "1"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "budget_locked"
    assert owner.delete(f"/api/v1/budgets/{b['id']}").status_code == 409

    second = owner.post(f"/api/v1/projects/{project['id']}/budgets", json={"name": "Another"}).json()
    owner.post(f"/api/v1/budgets/{second['id']}/lines", json={"description": "x", "amount": "1"})
    dup = owner.post(f"/api/v1/budgets/{second['id']}/approve")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "budget_exists"
    assert owner.delete(f"/api/v1/budgets/{second['id']}").status_code == 204

    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        with pytest.raises(DBAPIError, match="cannot be changed"):
            conn.execute(text("UPDATE budget_lines SET amount = 1"))
        conn.rollback()
    engine.dispose()

    dash = owner.get("/api/v1/dashboard/summary").json()
    usd = next(r for r in dash["original_budget"] if r["currency"] == "USD")
    assert usd["amount"] == "105000.00" and usd["project_count"] == 1
    assert "Original budget" not in dash["unavailable_metrics"]


def test_budget_permissions(priced_estimate) -> None:  # type: ignore[no-untyped-def]
    owner, project = priced_estimate["owner"], priced_estimate["project"]
    field = invite_and_join(owner, "field_engineer")
    owner.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": field.user_id, "project_role": "field_engineer"})
    assert field.get(f"/api/v1/projects/{project['id']}/budgets").status_code == 403
    assert field.get("/api/v1/dashboard/summary").json()["original_budget"] is None
