from __future__ import annotations

import time

import pyotp
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, register, unique_email


def test_register_creates_owner_membership(client: TestClient) -> None:
    acct = register(client, org="Lone Star Concrete")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {acct.token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == acct.email
    assert body["memberships"][0]["tenant_name"] == "Lone Star Concrete"
    assert body["memberships"][0]["role_key"] == "owner"
    assert "password_hash" not in me.text


def test_register_rejects_weak_password_and_duplicate_email(client: TestClient) -> None:
    weak = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": unique_email(),
                                                       "password": "short", "organization_name": "X Co"})
    assert weak.status_code == 422
    acct = register(client)
    dup = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": acct.email.upper(),
                                                      "password": PASSWORD, "organization_name": "Y Co"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "email_taken"


def test_register_rejects_unknown_fields_and_bad_state(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": unique_email(), "password": PASSWORD,
                                                       "organization_name": "X Co", "home_state": "ZZ"})
    assert resp.status_code == 422
    resp = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": unique_email(), "password": PASSWORD,
                                                       "organization_name": "X Co", "is_admin": True})
    assert resp.status_code == 422


def test_login_success_and_failure_are_indistinguishable(client: TestClient) -> None:
    acct = register(client)
    ok = client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["session"]["user"]["id"] == acct.user_id
    wrong_pw = client.post("/api/v1/auth/login", json={"email": acct.email, "password": "wrong-password-123"})
    no_user = client.post("/api/v1/auth/login", json={"email": unique_email(), "password": "wrong-password-123"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_login_rate_limited(client: TestClient) -> None:
    acct = register(client)
    codes = [client.post("/api/v1/auth/login", json={"email": acct.email, "password": "bad-password-xx"}).status_code
             for _ in range(12)]
    assert 429 in codes


def test_unauthenticated_requests_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/projects", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_cookie_auth_requires_csrf_for_mutations(client: TestClient) -> None:
    acct = register(client)
    resp = client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    assert "qs_access" in resp.cookies and "qs_csrf" in resp.cookies
    headers = {"X-Tenant-ID": acct.tenant_id}
    # GET with cookie only: allowed
    assert client.get("/api/v1/tenant", headers=headers).status_code == 200
    body = {"number": "C-1", "name": "Cookie Project", "sector": "commercial", "delivery_method": "design_build",
            "contract_type": "lump_sum"}
    # POST without CSRF header: rejected
    denied = client.post("/api/v1/projects", headers=headers, json=body)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "csrf_failed"
    # POST with matching CSRF header: allowed
    ok = client.post("/api/v1/projects", headers={**headers, "X-CSRF-Token": client.cookies["qs_csrf"]}, json=body)
    assert ok.status_code == 201, ok.text
    client.cookies.clear()


def test_refresh_rotates_and_detects_reuse(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.domains.identity import service

    acct = register(client)
    client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    first = client.cookies.get("qs_refresh")
    assert first
    r1 = client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200
    second = client.cookies.get("qs_refresh")
    assert second and second != first

    # Replaying the rotated token inside the grace window is rejected without revoking the family.
    client.cookies.set("qs_refresh", first, path="/api/v1/auth")
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_superseded"

    # Outside the grace window, reuse revokes the whole family (including the newest token).
    monkeypatch.setattr(service, "REFRESH_REUSE_GRACE_SECONDS", -1)
    client.cookies.clear()
    client.cookies.set("qs_refresh", first, path="/api/v1/auth")
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_reused"
    client.cookies.clear()
    client.cookies.set("qs_refresh", second, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.clear()


def test_logout_revokes_refresh(client: TestClient) -> None:
    acct = register(client)
    client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    token = client.cookies.get("qs_refresh")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("qs_refresh", token, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.clear()


def test_change_password_revokes_sessions(client: TestClient) -> None:
    acct = register(client)
    client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    old_refresh = client.cookies.get("qs_refresh")
    client.cookies.clear()
    h = {"Authorization": f"Bearer {acct.token}"}
    bad = client.post("/api/v1/auth/password", headers=h, json={"current_password": "nope-nope-nope",
                                                                "new_password": "Another-Strong-Pass-1"})
    assert bad.status_code == 422
    ok = client.post("/api/v1/auth/password", headers=h, json={"current_password": PASSWORD,
                                                               "new_password": "Another-Strong-Pass-1"})
    assert ok.status_code == 204
    client.cookies.set("qs_refresh", old_refresh, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": acct.email,
                                                   "password": "Another-Strong-Pass-1"}).status_code == 200
    client.cookies.clear()


def _next_code(secret: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.at(int(time.time()) + 30)


def test_mfa_enrolment_login_and_replay_protection(client: TestClient) -> None:
    acct = register(client)
    h = {"Authorization": f"Bearer {acct.token}"}
    assert client.post("/api/v1/auth/mfa/setup", headers=h, json={"password": "wrong"}).status_code == 422
    setup = client.post("/api/v1/auth/mfa/setup", headers=h, json={"password": PASSWORD})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    assert client.post("/api/v1/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 422
    current = pyotp.TOTP(secret).now()
    enabled = client.post("/api/v1/auth/mfa/enable", headers=h, json={"code": current})
    assert enabled.status_code == 200 and enabled.json()["mfa_enabled"] is True

    login = client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD})
    assert login.status_code == 200
    body = login.json()
    assert body["mfa_required"] is True and body["session"] is None and "qs_access" not in login.cookies
    # Replaying the code used at enrolment is rejected.
    replay = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": current})
    assert replay.status_code == 401
    ok = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": _next_code(secret)})
    assert ok.status_code == 200, ok.text
    assert ok.json()["session"]["user"]["mfa_enabled"] is True
    client.cookies.clear()


def test_mfa_token_cannot_be_used_as_access_token(client: TestClient) -> None:
    acct = register(client)
    h = {"Authorization": f"Bearer {acct.token}"}
    secret = client.post("/api/v1/auth/mfa/setup", headers=h, json={"password": PASSWORD}).json()["secret"]
    client.post("/api/v1/auth/mfa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()})
    mfa_token = client.post("/api/v1/auth/login", json={"email": acct.email, "password": PASSWORD}).json()["mfa_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert resp.status_code == 401
