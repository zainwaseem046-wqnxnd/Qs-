"""US + UK markets, regional data residency guard, and email-driven flows (invitations, password reset)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.core import email
from app.core.config import get_settings
from app.core.regions import normalise_postal_code
from tests.conftest import PASSWORD, Account, make_project, register, role_id, unique_email


@pytest.fixture(autouse=True)
def _clean_outbox() -> None:
    email.clear_outbox()


def register_uk(client: TestClient, org: str = "Thames Quantity Surveyors") -> Account:
    resp = client.post("/api/v1/auth/register", json={
        "full_name": "Alex Surveyor", "email": unique_email("uk"), "password": PASSWORD,
        "organization_name": org, "country_code": "GB",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    client.cookies.clear()
    return Account(client, body["session"]["user"]["email"], body["session"]["user"]["id"],
                   body["session"]["memberships"][0]["tenant_id"], body["access_token"])


# --- countries ---------------------------------------------------------------------------------
def test_uk_organization_gets_uk_defaults(client: TestClient) -> None:
    uk = register_uk(client)
    t = uk.get("/api/v1/tenant").json()["tenant"]
    assert (t["country_code"], t["default_currency"], t["measurement_system"], t["timezone"], t["data_region"]) == (
        "GB", "GBP", "metric", "Europe/London", get_settings().deployment_region)
    assert t["home_state"] is None


def test_us_organization_keeps_us_defaults(owner) -> None:  # type: ignore[no-untyped-def]
    t = owner.get("/api/v1/tenant").json()["tenant"]
    assert (t["country_code"], t["default_currency"], t["measurement_system"]) == ("US", "USD", "us_customary")


def test_registration_rejects_state_for_uk_and_unknown_country(client: TestClient) -> None:
    base = {"full_name": "A B", "email": unique_email(), "password": PASSWORD, "organization_name": "Co Ltd"}
    assert client.post("/api/v1/auth/register", json={**base, "country_code": "GB", "home_state": "TX"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={**base, "country_code": "FR"}).status_code == 422


def test_uk_project_defaults_to_gbp_and_validates_postcode(client: TestClient) -> None:
    uk = register_uk(client)
    p = make_project(uk, original_contract_value="4250000.00", delivery_method="design_and_build", contract_type="jct_db",
                     site_address={"line1": "1 Canada Square", "city": "London", "county": "Greater London",
                                   "postal_code": "e14  5ab"})
    assert p["currency"] == "GBP" and p["our_role"] == "main_contractor"
    assert p["site_address"]["postal_code"] == "E14 5AB" and p["site_address"]["country_code"] == "GB"
    bad = uk.post("/api/v1/projects", json={"number": "UK-2", "name": "Bad Postcode", "sector": "commercial",
                                            "delivery_method": "traditional", "contract_type": "jct_sbc",
                                            "site_address": {"postal_code": "12345"}})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["field"] == "site_address.postal_code"
    state = uk.post("/api/v1/projects", json={"number": "UK-3", "name": "Has State", "sector": "commercial",
                                              "delivery_method": "traditional", "contract_type": "jct_sbc",
                                              "site_address": {"state_code": "TX"}})
    assert state.status_code == 422


def test_explicit_us_address_inside_uk_organization(client: TestClient) -> None:
    uk = register_uk(client)
    co = uk.post("/api/v1/companies", json={"name": "Texas Partner LLC", "company_type": "consultant",
                                            "address": {"country_code": "US", "state_code": "tx", "postal_code": "78701"}})
    assert co.status_code == 201, co.text
    assert co.json()["address"]["state_code"] == "TX"


def test_uk_tenant_cannot_set_us_home_state_but_can_change_units(client: TestClient) -> None:
    uk = register_uk(client)
    assert uk.patch("/api/v1/tenant", json={"home_state": "TX"}).status_code == 422
    resp = uk.patch("/api/v1/tenant", json={"measurement_system": "us_customary"})
    assert resp.status_code == 200 and resp.json()["measurement_system"] == "us_customary"


@pytest.mark.parametrize(("raw", "expected"), [("sw1a1aa", "SW1A 1AA"), ("M1 1AE", "M1 1AE"), ("B33 8TH", "B33 8TH"),
                                               ("cr2 6xh", "CR2 6XH"), ("DN55 1PT", "DN55 1PT")])
def test_uk_postcode_normalisation(raw: str, expected: str) -> None:
    assert normalise_postal_code("GB", raw) == expected


def test_vocabulary_lists_supported_countries(owner) -> None:  # type: ignore[no-untyped-def]
    v = owner.get("/api/v1/vocabulary").json()
    assert v["countries"] == {"US": "United States", "GB": "United Kingdom"}
    assert set(v["measurement_systems"]) == {"us_customary", "metric"}


# --- data residency guard ------------------------------------------------------------------------
def test_deployment_refuses_other_region_tenant(owner, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    other = "uk" if get_settings().deployment_region == "us" else "us"
    monkeypatch.setattr(get_settings(), "deployment_region", other)
    resp = owner.get("/api/v1/projects")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "tenant_wrong_region"


# --- invitation email -----------------------------------------------------------------------------
def test_invitation_is_emailed(owner) -> None:  # type: ignore[no-untyped-def]
    to = unique_email("invitee")
    inv = owner.post("/api/v1/tenant/invitations", json={"email": to, "role_id": role_id(owner, "viewer")}).json()
    assert inv["email_sent"] is True
    [msg] = email.outbox()
    assert msg.to == to and "Acme Builders" in msg.subject
    assert inv["accept_url"] in msg.text and msg.html and inv["accept_url"] in msg.html


def test_email_html_escapes_untrusted_values(client: TestClient) -> None:
    acct = register(client, org="<script>alert(1)</script> Builders")
    acct.post("/api/v1/tenant/invitations", json={"email": unique_email(), "role_id": role_id(acct, "viewer")})
    [msg] = email.outbox()
    assert msg.html and "<script>" not in msg.html and "&lt;script&gt;" in msg.html


# --- password reset ---------------------------------------------------------------------------------
def _reset_token() -> str:
    [msg] = [m for m in email.outbox() if "Reset" in m.subject]
    match = re.search(r"/reset-password/([A-Za-z0-9_-]+)", msg.text)
    assert match
    return match.group(1)


def test_password_reset_flow(client: TestClient, owner) -> None:  # type: ignore[no-untyped-def]
    client.post("/api/v1/auth/login", json={"email": owner.email, "password": PASSWORD})
    old_refresh = client.cookies.get("qs_refresh")
    client.cookies.clear()

    resp = client.post("/api/v1/auth/password/forgot", json={"email": owner.email.upper()})
    assert resp.status_code == 202
    token = _reset_token()
    new = "Brand-New-Passphrase-42"
    assert client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": new}).status_code == 204
    assert any("password was changed" in m.subject for m in email.outbox())
    # single use
    again = client.post("/api/v1/auth/password/reset", json={"token": token, "new_password": "Another-Passphrase-77"})
    assert again.status_code == 422 and again.json()["error"]["code"] == "reset_token_invalid"
    # old sessions revoked, old password dead, new one works
    client.cookies.set("qs_refresh", old_refresh, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"email": owner.email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": owner.email, "password": new}).status_code == 200
    client.cookies.clear()


def test_forgot_password_does_not_reveal_accounts(client: TestClient, owner) -> None:  # type: ignore[no-untyped-def]
    known = client.post("/api/v1/auth/password/forgot", json={"email": owner.email})
    unknown = client.post("/api/v1/auth/password/forgot", json={"email": unique_email("nobody")})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(email.outbox()) == 1


def test_only_newest_reset_link_works_and_expired_links_fail(client: TestClient, owner, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client.post("/api/v1/auth/password/forgot", json={"email": owner.email})
    first = _reset_token()
    email.clear_outbox()
    client.post("/api/v1/auth/password/forgot", json={"email": owner.email})
    second = _reset_token()
    assert client.post("/api/v1/auth/password/reset",
                       json={"token": first, "new_password": "Brand-New-Passphrase-42"}).status_code == 422
    monkeypatch.setattr(get_settings(), "password_reset_ttl_seconds", -1)
    email.clear_outbox()
    client.post("/api/v1/auth/password/forgot", json={"email": owner.email})
    expired = _reset_token()
    assert client.post("/api/v1/auth/password/reset",
                       json={"token": expired, "new_password": "Brand-New-Passphrase-42"}).status_code == 422
    del second


def test_reset_rejects_weak_password(client: TestClient, owner) -> None:  # type: ignore[no-untyped-def]
    client.post("/api/v1/auth/password/forgot", json={"email": owner.email})
    assert client.post("/api/v1/auth/password/reset",
                       json={"token": _reset_token(), "new_password": "short"}).status_code == 422


def test_forgot_password_rate_limited_per_email(client: TestClient, owner) -> None:  # type: ignore[no-untyped-def]
    codes = [client.post("/api/v1/auth/password/forgot", json={"email": owner.email}).status_code for _ in range(5)]
    assert codes[:3] == [202, 202, 202] and 429 in codes[3:]


def test_production_requires_smtp(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import Settings
    with pytest.raises(ValueError, match="SMTP"):
        Settings(environment="production", jwt_secret="x" * 40, cookie_secure=True,
                 field_encryption_key="ZmFrZS1rZXktZm9yLXRlc3RzLW9ubHktMDEyMzQ1Njc4OWE=", email_backend="console")


def test_uk_and_us_contract_vocabularies_are_country_specific(client: TestClient, owner) -> None:  # type: ignore[no-untyped-def]
    uk = register_uk(client)
    v = uk.get("/api/v1/vocabulary").json()
    assert "nec4_ecc_c" in v["contract_types"] and "gmp" not in v["contract_types"]
    assert "two_stage_tender" in v["delivery_methods"] and "quantity_surveyor" in v["our_roles"]
    us_terms = uk.post("/api/v1/projects", json={"number": "UK-9", "name": "US Terms", "sector": "commercial",
                                                 "delivery_method": "cm_at_risk", "contract_type": "gmp"})
    assert us_terms.status_code == 422
    nec = make_project(uk, delivery_method="two_stage_tender", contract_type="nec4_ecc_c", our_role="quantity_surveyor")
    assert nec["contract_type"] == "nec4_ecc_c"
    assert owner.post("/api/v1/projects", json={"number": "US-9", "name": "UK Terms", "sector": "commercial",
                                                "delivery_method": "traditional", "contract_type": "jct_sbc"}).status_code == 422
    assert "gmp" in owner.get("/api/v1/vocabulary").json()["contract_types"]
