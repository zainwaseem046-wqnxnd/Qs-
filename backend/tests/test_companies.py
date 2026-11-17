from __future__ import annotations


def test_company_crud_with_contacts_and_versioning(owner) -> None:  # type: ignore[no-untyped-def]
    created = owner.post("/api/v1/companies", json={
        "name": "Gulf Coast Electric", "company_type": "subcontractor", "trades": ["Electrical", " Low Voltage ", ""],
        "email": "bids@gulfcoast.example", "address": {"city": "Houston", "state_code": "TX", "postal_code": "77002"},
    })
    assert created.status_code == 201, created.text
    co = created.json()
    assert co["trades"] == ["Electrical", "Low Voltage"] and co["address"]["city"] == "Houston"

    upd = owner.patch(f"/api/v1/companies/{co['id']}", json={"version": 1, "phone": "713-555-0100", "address": None})
    assert upd.status_code == 200 and upd.json()["version"] == 2 and upd.json()["address"] is None
    stale = owner.patch(f"/api/v1/companies/{co['id']}", json={"version": 1, "phone": "x"})
    assert stale.status_code == 409

    contact = owner.post(f"/api/v1/companies/{co['id']}/contacts", json={
        "first_name": "Maria", "last_name": "Lopez", "title": "Estimator", "email": "maria@gulfcoast.example"})
    assert contact.status_code == 201
    cid = contact.json()["id"]
    put = owner.put(f"/api/v1/companies/{co['id']}/contacts/{cid}",
                    json={"first_name": "Maria", "last_name": "Lopez", "title": "Chief Estimator"})
    assert put.json()["title"] == "Chief Estimator"
    assert len(owner.get(f"/api/v1/companies/{co['id']}/contacts").json()) == 1
    assert owner.delete(f"/api/v1/companies/{co['id']}/contacts/{cid}").status_code == 204

    bad = owner.post("/api/v1/companies", json={"name": "X", "company_type": "pirate"})
    assert bad.status_code == 422
    bad_email = owner.post("/api/v1/companies", json={"name": "X", "company_type": "other", "email": "nope"})
    assert bad_email.status_code == 422


def test_company_search_and_inactive_filter(owner) -> None:  # type: ignore[no-untyped-def]
    a = owner.post("/api/v1/companies", json={"name": "Apex Steel Erectors", "company_type": "subcontractor"}).json()
    owner.post("/api/v1/companies", json={"name": "Bluebonnet Architects", "company_type": "architect"})
    assert owner.get("/api/v1/companies?q=apex").json()["total"] == 1
    assert owner.get("/api/v1/companies?company_type=architect").json()["total"] == 1
    owner.patch(f"/api/v1/companies/{a['id']}", json={"version": 1, "is_active": False})
    assert owner.get("/api/v1/companies?q=apex").json()["total"] == 0
    assert owner.get("/api/v1/companies?q=apex&include_inactive=true").json()["total"] == 1
