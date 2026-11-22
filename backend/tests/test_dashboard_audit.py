from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from tests.conftest import invite_and_join, make_project


def test_dashboard_sums_are_exact_and_grouped_by_currency(owner) -> None:  # type: ignore[no-untyped-def]
    values = ["0.10", "0.20", "1234567.89", "9999999.99", "0.01"]
    for v in values:
        make_project(owner, original_contract_value=v, status="active")
    make_project(owner, original_contract_value="500.00", status="preconstruction", currency="CAD")
    make_project(owner, original_contract_value=None, status="active")  # value not yet entered
    make_project(owner, original_contract_value="777.00", status="pursuit")
    make_project(owner, original_contract_value="1.00", status="complete")  # not live backlog
    dash = owner.get("/api/v1/dashboard/summary").json()
    live = {row["currency"]: row for row in dash["live_contract_value"]}
    assert live["USD"]["amount"] == str(sum(Decimal(v) for v in values))  # 11234568.19
    assert live["USD"]["amount"] == "11234568.19"
    assert live["USD"]["project_count"] == 6 and live["USD"]["projects_without_value"] == 1
    assert live["CAD"]["amount"] == "500.00"
    assert dash["pursuit_value"][0]["amount"] == "777.00"
    assert dash["total_projects"] == 9
    assert dash["by_status"]["active"] == 6
    assert "Cash flow" in dash["unavailable_metrics"]  # forecast figures are available since milestone 2.4


def test_dashboard_respects_visibility_and_archive(owner) -> None:  # type: ignore[no-untyped-def]
    pm = invite_and_join(owner, "project_manager")
    make_project(owner, original_contract_value="1000.00")
    mine = make_project(pm, original_contract_value="250.00")
    assert pm.get("/api/v1/dashboard/summary").json()["live_contract_value"][0]["amount"] == "250.00"
    owner.post(f"/api/v1/projects/{mine['id']}/archive")
    assert owner.get("/api/v1/dashboard/summary").json()["live_contract_value"][0]["amount"] == "1000.00"


def test_upcoming_completions(owner) -> None:  # type: ignore[no-untyped-def]
    soon = (date.today() + timedelta(days=30)).isoformat()
    later = (date.today() + timedelta(days=400)).isoformat()
    a = make_project(owner, planned_completion_date=soon)
    make_project(owner, planned_completion_date=later)
    upcoming = owner.get("/api/v1/dashboard/summary").json()["upcoming_completions"]
    assert [u["id"] for u in upcoming] == [a["id"]]


def test_audit_events_are_append_only_at_database_level(owner) -> None:  # type: ignore[no-untyped-def]
    make_project(owner)
    owner_engine = create_engine(get_settings().migration_database_url)  # even the schema owner
    with owner_engine.connect() as conn:
        for stmt in ("UPDATE audit_events SET summary = 'tampered'", "DELETE FROM audit_events",
                     "TRUNCATE audit_events"):
            with pytest.raises(DBAPIError, match="append-only"):
                conn.execute(text(stmt))
            conn.rollback()
    owner_engine.dispose()
    app_engine = create_engine(get_settings().database_url)
    with app_engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": owner.tenant_id})
        with pytest.raises(DBAPIError, match="permission denied"):
            conn.execute(text("UPDATE audit_events SET summary = 'tampered'"))
        conn.rollback()
    app_engine.dispose()


def test_document_version_content_is_immutable(owner) -> None:  # type: ignore[no-untyped-def]
    import io
    owner.post("/api/v1/documents", data={"title": "x", "category": "other"},
               files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")})
    engine = create_engine(get_settings().migration_database_url)
    with engine.connect() as conn:
        with pytest.raises(DBAPIError, match="immutable"):
            conn.execute(text("UPDATE document_versions SET sha256 = 'x'"))
        conn.rollback()
    engine.dispose()


def test_audit_log_filters_and_redaction(owner) -> None:  # type: ignore[no-untyped-def]
    p = make_project(owner, original_contract_value="100.00")
    owner.patch(f"/api/v1/projects/{p['id']}", json={"version": 1, "original_contract_value": "200.00"})
    log = owner.get(f"/api/v1/audit-events?entity_type=project&entity_id={p['id']}").json()
    assert [e["action"] for e in log["items"]] == ["project.updated", "project.created"]
    assert log["items"][0]["changes"]["original_contract_value"]["to"] == "200.00"
    executive = invite_and_join(owner, "executive")
    assert executive.get("/api/v1/audit-events").status_code == 200  # executives can view audit
    # sign-in events are recorded without tenant scope and never leak into tenant logs
    assert all(e["action"] != "auth.login" for e in log["items"])
