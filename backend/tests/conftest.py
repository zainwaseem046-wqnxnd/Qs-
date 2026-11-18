"""Test fixtures.

Tests run against a real PostgreSQL database (``qs_test``). The API connects as the restricted runtime
role (``qs_app``), exactly as in production, so Row-Level Security is exercised by every test.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

os.environ.setdefault("QS_ENVIRONMENT", "test")
os.environ.setdefault("QS_DATABASE_URL", "postgresql+psycopg://qs_app:qs_app_dev@localhost:5432/qs_test")
os.environ.setdefault("QS_MIGRATION_DATABASE_URL", "postgresql+psycopg://qs_owner:qs_owner_dev@localhost:5432/qs_test")
os.environ.setdefault("QS_STORAGE_LOCAL_PATH", tempfile.mkdtemp(prefix="qs-test-storage-"))
os.environ.setdefault("QS_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))
os.environ.setdefault("QS_EMAIL_BACKEND", "memory")
os.environ.setdefault("QS_EMAIL_FROM_ADDRESS", "no-reply@example.com")

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.core.config import get_settings
from app.core.ratelimit import reset_rate_limits
from app.main import create_app

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.attributes["database_url"] = get_settings().migration_database_url
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _reset_limits() -> None:
    reset_rate_limits()


@pytest.fixture(scope="session")
def app():  # type: ignore[no-untyped-def]
    return create_app()


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        yield c


@dataclass
class Account:
    """An authenticated user acting in one tenant, using Bearer auth (no cookies)."""

    client: TestClient
    email: str
    user_id: str
    tenant_id: str
    token: str
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Tenant-ID": self.tenant_id, **self.extra_headers}

    def get(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.post(url, headers=self.headers, **kw)

    def patch(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.patch(url, headers=self.headers, **kw)

    def put(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.put(url, headers=self.headers, **kw)

    def delete(self, url: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self.client.delete(url, headers=self.headers, **kw)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def register(client: TestClient, *, org: str = "Acme Builders", email: str | None = None,
             full_name: str = "Pat Owner") -> Account:
    email = email or unique_email("owner")
    resp = client.post("/api/v1/auth/register", json={
        "full_name": full_name, "email": email, "password": PASSWORD, "organization_name": org, "home_state": "TX",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    client.cookies.clear()  # tests use Bearer auth unless they opt into cookies
    return Account(client, email, body["session"]["user"]["id"], body["session"]["memberships"][0]["tenant_id"],
                   body["access_token"])


def login(client: TestClient, email: str, tenant_id: str, password: str = PASSWORD) -> Account:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    client.cookies.clear()
    return Account(client, email, body["session"]["user"]["id"], tenant_id, body["access_token"])


def role_id(account: Account, key: str) -> str:
    roles = account.get("/api/v1/tenant/roles").json()
    return next(r["id"] for r in roles if r["key"] == key)


def invite_and_join(owner: Account, role_key: str, full_name: str = "Team Member") -> Account:
    email = unique_email(role_key)
    inv = owner.post("/api/v1/tenant/invitations", json={"email": email, "role_id": role_id(owner, role_key)})
    assert inv.status_code == 201, inv.text
    token = inv.json()["accept_url"].rsplit("/", 1)[1]
    resp = owner.client.post(f"/api/v1/auth/invitations/{token}/accept",
                             json={"full_name": full_name, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    owner.client.cookies.clear()
    return Account(owner.client, email, body["session"]["user"]["id"], owner.tenant_id, body["access_token"])


def make_project(account: Account, **overrides: Any) -> dict[str, Any]:
    payload = {
        "number": overrides.pop("number", f"P-{uuid.uuid4().hex[:6]}"),
        "name": "Riverside Medical Office Building",
        "status": "active",
        "sector": "commercial",
        "delivery_method": "cm_at_risk",
        "contract_type": "gmp",
        "original_contract_value": "12500000.00",
        **overrides,
    }
    resp = account.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def owner(client: TestClient) -> Account:
    return register(client)
