from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.tenancy.models import Permission
from app.domains.tenancy.permissions import PERMISSION_CATALOG, SYSTEM_ROLES
from tests.conftest import PASSWORD, invite_and_join, make_project, register, role_id, unique_email


def test_permission_catalog_matches_database() -> None:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        keys = set(db.scalars(select(Permission.key)))
    engine.dispose()
    assert keys == set(PERMISSION_CATALOG)


def test_system_roles_match_definitions(owner) -> None:  # type: ignore[no-untyped-def]
    roles = {r["key"]: set(r["permission_keys"]) for r in owner.get("/api/v1/tenant/roles").json()}
    for key, spec in SYSTEM_ROLES.items():
        assert roles[key] == {str(p) for p in spec["permissions"]}, key  # type: ignore[union-attr]


def test_invitation_flow_and_single_use(owner) -> None:  # type: ignore[no-untyped-def]
    email = unique_email("pm")
    inv = owner.post("/api/v1/tenant/invitations", json={"email": email, "role_id": role_id(owner, "project_manager")})
    assert inv.status_code == 201
    token = inv.json()["accept_url"].rsplit("/", 1)[1]
    preview = owner.client.get(f"/api/v1/auth/invitations/{token}")
    assert preview.status_code == 200
    assert preview.json()["role_name"] == "Project Manager" and preview.json()["account_exists"] is False
    accepted = owner.client.post(f"/api/v1/auth/invitations/{token}/accept",
                                 json={"full_name": "Jamie PM", "password": PASSWORD})
    assert accepted.status_code == 200
    owner.client.cookies.clear()
    again = owner.client.post(f"/api/v1/auth/invitations/{token}/accept",
                              json={"full_name": "Jamie PM", "password": PASSWORD})
    assert again.status_code == 404
    statuses = {i["email"]: i["status"] for i in owner.get("/api/v1/tenant/invitations").json()}
    assert statuses[email] == "accepted"
    assert any(m["email"] == email for m in owner.get("/api/v1/tenant/members").json())


def test_existing_user_joins_second_tenant_with_password(client) -> None:  # type: ignore[no-untyped-def]
    a = register(client, org="Org A")
    b = register(client, org="Org B")
    inv = b.post("/api/v1/tenant/invitations", json={"email": a.email, "role_id": role_id(b, "viewer")})
    token = inv.json()["accept_url"].rsplit("/", 1)[1]
    assert client.get(f"/api/v1/auth/invitations/{token}").json()["account_exists"] is True
    bad = client.post(f"/api/v1/auth/invitations/{token}/accept", json={"password": "wrong-password-1"})
    assert bad.status_code == 422
    ok = client.post(f"/api/v1/auth/invitations/{token}/accept", json={"password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["session"] is None  # must sign in normally (MFA enforced)
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {a.token}"}).json()
    assert {m["tenant_name"] for m in me["memberships"]} == {"Org A", "Org B"}


def test_revoked_invitation_cannot_be_used(owner) -> None:  # type: ignore[no-untyped-def]
    inv = owner.post("/api/v1/tenant/invitations", json={"email": unique_email(), "role_id": role_id(owner, "viewer")})
    token = inv.json()["accept_url"].rsplit("/", 1)[1]
    assert owner.delete(f"/api/v1/tenant/invitations/{inv.json()['id']}").status_code == 204
    assert owner.client.get(f"/api/v1/auth/invitations/{token}").status_code == 404


def test_viewer_permissions_enforced(owner) -> None:  # type: ignore[no-untyped-def]
    viewer = invite_and_join(owner, "viewer")
    body = {"number": "V-1", "name": "Nope", "sector": "commercial", "delivery_method": "design_build",
            "contract_type": "lump_sum"}
    assert viewer.post("/api/v1/projects", json=body).status_code == 403
    assert viewer.post("/api/v1/companies", json={"name": "x", "company_type": "other"}).status_code == 403
    assert viewer.get("/api/v1/tenant/members").status_code == 403
    assert viewer.get("/api/v1/audit-events").status_code == 403
    assert viewer.patch("/api/v1/tenant", json={"name": "Hacked"}).status_code == 403


def test_project_visibility_by_membership(owner) -> None:  # type: ignore[no-untyped-def]
    pm = invite_and_join(owner, "project_manager")
    hidden = make_project(owner, name="Owner Only Tower")
    mine = make_project(pm, name="PM Created Clinic")
    pm_ids = {p["id"] for p in pm.get("/api/v1/projects").json()["items"]}
    assert mine["id"] in pm_ids and hidden["id"] not in pm_ids
    assert pm.get(f"/api/v1/projects/{hidden['id']}").status_code == 404
    # Adding the PM to the team grants visibility.
    add = owner.post(f"/api/v1/projects/{hidden['id']}/members",
                     json={"user_id": pm.user_id, "project_role": "project_manager"})
    assert add.status_code == 201
    assert pm.get(f"/api/v1/projects/{hidden['id']}").status_code == 200
    # Owner (projects.view_all) sees both.
    owner_ids = {p["id"] for p in owner.get("/api/v1/projects").json()["items"]}
    assert {hidden["id"], mine["id"]} <= owner_ids


def test_financials_hidden_without_permission(owner) -> None:  # type: ignore[no-untyped-def]
    field = invite_and_join(owner, "field_engineer")
    project = make_project(owner, original_contract_value="987654.32", retainage_percent="5.00")
    owner.post(f"/api/v1/projects/{project['id']}/members",
               json={"user_id": field.user_id, "project_role": "field_engineer"})
    seen = field.get(f"/api/v1/projects/{project['id']}").json()
    assert seen["original_contract_value"] is None and seen["retainage_percent"] is None
    assert seen["financials_visible"] is False and seen["can_edit"] is False
    listing = field.get("/api/v1/projects").json()["items"][0]
    assert listing["original_contract_value"] is None
    dash = field.get("/api/v1/dashboard/summary").json()
    assert dash["live_contract_value"] is None and dash["financials_visible"] is False
    activity = field.get(f"/api/v1/projects/{project['id']}/activity").json()["items"]
    created = next(e for e in activity if e["action"] == "project.created")
    assert "987654.32" not in str(created)


def test_cannot_grant_permissions_you_do_not_hold(owner) -> None:  # type: ignore[no-untyped-def]
    cm = invite_and_join(owner, "commercial_manager")
    # commercial_manager lacks members.manage: cannot invite at all
    assert cm.post("/api/v1/tenant/invitations",
                   json={"email": unique_email(), "role_id": role_id(owner, "viewer")}).status_code == 403
    admin = invite_and_join(owner, "administrator")
    # administrators cannot grant the owner role
    resp = admin.post("/api/v1/tenant/invitations",
                      json={"email": unique_email(), "role_id": role_id(owner, "owner")})
    assert resp.status_code == 403
    # custom role creation is limited to held permissions (admin holds all, so use a limited custom role)
    custom = owner.post("/api/v1/tenant/roles", json={"name": "Estimator", "permissions": ["dashboard.view",
                                                                                         "documents.view"]})
    assert custom.status_code == 201
    unknown = owner.post("/api/v1/tenant/roles", json={"name": "Bad", "permissions": ["root.everything"]})
    assert unknown.status_code == 422


def test_last_owner_cannot_be_demoted_or_removed(owner) -> None:  # type: ignore[no-untyped-def]
    members = owner.get("/api/v1/tenant/members").json()
    me = next(m for m in members if m["user_id"] == owner.user_id)
    demote = owner.patch(f"/api/v1/tenant/members/{me['id']}", json={"role_id": role_id(owner, "viewer")})
    assert demote.status_code == 409
    admin = invite_and_join(owner, "administrator")
    assert admin.delete(f"/api/v1/tenant/members/{me['id']}").status_code == 403
    assert admin.patch(f"/api/v1/tenant/members/{me['id']}", json={"status": "suspended"}).status_code == 403


def test_suspended_member_loses_access(owner) -> None:  # type: ignore[no-untyped-def]
    viewer = invite_and_join(owner, "viewer")
    member = next(m for m in owner.get("/api/v1/tenant/members").json() if m["user_id"] == viewer.user_id)
    assert owner.patch(f"/api/v1/tenant/members/{member['id']}", json={"status": "suspended"}).status_code == 200
    assert viewer.get("/api/v1/projects").status_code == 403
    assert owner.patch(f"/api/v1/tenant/members/{member['id']}", json={"status": "active"}).status_code == 200
    assert viewer.get("/api/v1/projects").status_code == 200


def test_custom_role_lifecycle(owner) -> None:  # type: ignore[no-untyped-def]
    created = owner.post("/api/v1/tenant/roles", json={"name": "Site Admin", "permissions": ["dashboard.view"]}).json()
    updated = owner.patch(f"/api/v1/tenant/roles/{created['id']}",
                          json={"permissions": ["dashboard.view", "documents.view"]})
    assert updated.status_code == 200 and updated.json()["permission_keys"] == ["dashboard.view", "documents.view"]
    system = role_id(owner, "viewer")
    assert owner.patch(f"/api/v1/tenant/roles/{system}", json={"name": "Renamed"}).status_code == 403
    assert owner.delete(f"/api/v1/tenant/roles/{created['id']}").status_code == 204


def test_custom_roles_are_tenant_private(client) -> None:  # type: ignore[no-untyped-def]
    a = register(client, org="Org A")
    b = register(client, org="Org B")
    created = a.post("/api/v1/tenant/roles", json={"name": "Secret Role", "permissions": ["dashboard.view"]}).json()
    assert all(r["id"] != created["id"] for r in b.get("/api/v1/tenant/roles").json())
    resp = b.post("/api/v1/tenant/invitations", json={"email": unique_email(), "role_id": created["id"]})
    assert resp.status_code == 404
