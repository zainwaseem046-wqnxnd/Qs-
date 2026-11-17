from __future__ import annotations

from tests.conftest import invite_and_join, make_project


def test_create_and_get_project_with_address_and_client(owner) -> None:  # type: ignore[no-untyped-def]
    client_co = owner.post("/api/v1/companies", json={"name": "Hill Country Health", "company_type": "owner"}).json()
    p = make_project(owner, number="24-017", client_company_id=client_co["id"], retainage_percent="10",
                     site_address={"line1": "500 Congress Ave", "city": "Austin", "state_code": "tx",
                                   "postal_code": "78701", "county": "Travis"},
                     start_date="2026-01-05", planned_completion_date="2027-06-30", is_public_works=True,
                     prevailing_wage=True)
    got = owner.get(f"/api/v1/projects/{p['id']}").json()
    assert got["number"] == "24-017"
    assert got["client_company"]["name"] == "Hill Country Health"
    assert got["site_address"]["state_code"] == "TX"
    assert got["original_contract_value"] == "12500000.00"
    assert got["retainage_percent"] == "10.00"
    assert got["is_public_works"] is True and got["version"] == 1 and got["can_edit"] is True
    team = owner.get(f"/api/v1/projects/{p['id']}/members").json()
    assert [m["user_id"] for m in team] == [owner.user_id]


def test_validation_errors(owner) -> None:  # type: ignore[no-untyped-def]
    base = {"number": "V-2", "name": "Valid Name", "sector": "commercial", "delivery_method": "design_build",
            "contract_type": "lump_sum"}
    cases = [
        {"sector": "spaceport"},
        {"original_contract_value": -5},
        {"original_contract_value": "12.345"},
        {"original_contract_value": 1.5},
        {"start_date": "2026-05-01", "planned_completion_date": "2026-04-01"},
        {"retainage_percent": "150"},
        {"site_address": {"state_code": "XX"}},
        {"site_address": {"postal_code": "123"}},
        {"number": "bad number!"},
        {"currency": "BTC"},
    ]
    for override in cases:
        resp = owner.post("/api/v1/projects", json={**base, **override})
        assert resp.status_code == 422, (override, resp.text)
        assert resp.json()["error"]["code"] == "validation_failed"


def test_duplicate_project_number_rejected_case_insensitive(owner) -> None:  # type: ignore[no-untyped-def]
    make_project(owner, number="DUP-1")
    resp = owner.post("/api/v1/projects", json={"number": "dup-1", "name": "Other", "sector": "commercial",
                                                "delivery_method": "design_build", "contract_type": "lump_sum"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "duplicate_number"


def test_update_with_optimistic_concurrency_and_audit(owner) -> None:  # type: ignore[no-untyped-def]
    p = make_project(owner)
    ok = owner.patch(f"/api/v1/projects/{p['id']}",
                     json={"version": 1, "name": "Renamed Building", "original_contract_value": "13000000.00"})
    assert ok.status_code == 200 and ok.json()["version"] == 2
    stale = owner.patch(f"/api/v1/projects/{p['id']}", json={"version": 1, "name": "Lost Update"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "version_conflict"
    assert owner.get(f"/api/v1/projects/{p['id']}").json()["name"] == "Renamed Building"
    activity = owner.get(f"/api/v1/projects/{p['id']}/activity").json()["items"]
    update = next(e for e in activity if e["action"] == "project.updated")
    assert update["changes"]["original_contract_value"] == {"from": "12500000.00", "to": "13000000.00"}
    assert update["changes"]["name"]["to"] == "Renamed Building"
    assert update["actor_name"] == "Pat Owner"


def test_archive_makes_project_read_only(owner) -> None:  # type: ignore[no-untyped-def]
    p = make_project(owner)
    archived = owner.post(f"/api/v1/projects/{p['id']}/archive")
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    edit = owner.patch(f"/api/v1/projects/{p['id']}", json={"version": archived.json()["version"], "name": "Edited While Archived"})
    assert edit.status_code == 409 and edit.json()["error"]["code"] == "project_archived"
    assert all(i["id"] != p["id"] for i in owner.get("/api/v1/projects").json()["items"])
    assert any(i["id"] == p["id"] for i in owner.get("/api/v1/projects?include_archived=true").json()["items"])
    assert owner.post(f"/api/v1/projects/{p['id']}/restore").status_code == 200


def test_list_search_filter_sort(owner) -> None:  # type: ignore[no-untyped-def]
    make_project(owner, number="S-100", name="Alpha Elementary School", sector="institutional",
                 original_contract_value="100.00")
    make_project(owner, number="S-200", name="Bravo Distribution Center", sector="industrial",
                 original_contract_value="300.00", status="pursuit")
    make_project(owner, number="S-300", name="Charlie Apartments", sector="multifamily",
                 original_contract_value="200.00")
    q = owner.get("/api/v1/projects?q=bravo").json()
    assert [i["number"] for i in q["items"]] == ["S-200"]
    assert owner.get("/api/v1/projects?status=pursuit").json()["total"] == 1
    assert owner.get("/api/v1/projects?sector=industrial").json()["items"][0]["number"] == "S-200"
    by_value = owner.get("/api/v1/projects?sort=contract_value&order=desc").json()["items"]
    assert [i["number"] for i in by_value] == ["S-200", "S-300", "S-100"]
    paged = owner.get("/api/v1/projects?limit=2&offset=0&sort=number&order=asc").json()
    assert paged["total"] == 3 and len(paged["items"]) == 2


def test_team_parties_and_phases(owner) -> None:  # type: ignore[no-untyped-def]
    p = make_project(owner)
    pid = p["id"]
    engineer = invite_and_join(owner, "field_engineer", full_name="Field Fran")
    m = owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": engineer.user_id, "project_role": "superintendent"})
    assert m.status_code == 201 and m.json()["full_name"] == "Field Fran"
    dup = owner.post(f"/api/v1/projects/{pid}/members", json={"user_id": engineer.user_id, "project_role": "viewer"})
    assert dup.status_code == 409
    upd = owner.patch(f"/api/v1/projects/{pid}/members/{m.json()['id']}", json={"project_role": "field_engineer"})
    assert upd.status_code == 200 and upd.json()["project_role"] == "field_engineer"
    # field engineers cannot manage the team
    assert engineer.delete(f"/api/v1/projects/{pid}/members/{m.json()['id']}").status_code == 403
    assert owner.delete(f"/api/v1/projects/{pid}/members/{m.json()['id']}").status_code == 204

    arch = owner.post("/api/v1/companies", json={"name": "Studio Arc", "company_type": "architect"}).json()
    party = owner.post(f"/api/v1/projects/{pid}/parties", json={"company_id": arch["id"], "party_role": "architect"})
    assert party.status_code == 201 and party.json()["company"]["name"] == "Studio Arc"
    assert owner.post(f"/api/v1/projects/{pid}/parties",
                      json={"company_id": arch["id"], "party_role": "architect"}).status_code == 409
    assert owner.delete(f"/api/v1/projects/{pid}/parties/{party.json()['id']}").status_code == 204

    ph1 = owner.post(f"/api/v1/projects/{pid}/phases", json={"name": "Sitework", "start_date": "2026-01-01",
                                                            "end_date": "2026-03-01"}).json()
    ph2 = owner.post(f"/api/v1/projects/{pid}/phases", json={"name": "Structure"}).json()
    assert (ph1["sequence"], ph2["sequence"]) == (1, 2)
    bad = owner.post(f"/api/v1/projects/{pid}/phases", json={"name": "X", "start_date": "2026-05-01",
                                                            "end_date": "2026-01-01"})
    assert bad.status_code == 422
    upd_phase = owner.put(f"/api/v1/projects/{pid}/phases/{ph2['id']}", json={"name": "Structure", "status": "in_progress"})
    assert upd_phase.json()["status"] == "in_progress"
    assert owner.delete(f"/api/v1/projects/{pid}/phases/{ph1['id']}").status_code == 204
    actions = {e["action"] for e in owner.get(f"/api/v1/projects/{pid}/activity?limit=100").json()["items"]}
    assert {"project.member_added", "project.member_updated", "project.member_removed", "project.party_added",
            "project.party_removed", "project.phase_added", "project.phase_updated",
            "project.phase_deleted"} <= actions


def test_vocabulary_endpoint(owner) -> None:  # type: ignore[no-untyped-def]
    v = owner.get("/api/v1/vocabulary").json()
    assert v["delivery_methods"]["cm_at_risk"] == "Construction Manager at Risk"
    assert v["us_states"]["TX"] == "Texas" and "USD" in v["currencies"]
