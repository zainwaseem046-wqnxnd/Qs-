from __future__ import annotations

import hashlib
import io

from tests.conftest import invite_and_join, make_project

PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
ELF = b"\x7fELF\x02\x01\x01" + b"\x00" * 64


def _upload(acct, name="A-101.pdf", content=PDF, **data):  # type: ignore[no-untyped-def]
    fields = {"title": "Level 1 Floor Plan", "category": "drawing", **data}
    return acct.post("/api/v1/documents", data=fields, files={"file": (name, io.BytesIO(content), "application/pdf")})


def test_upload_version_download_roundtrip(owner) -> None:  # type: ignore[no-untyped-def]
    project = make_project(owner)
    resp = _upload(owner, project_id=project["id"], discipline="architectural", document_number="A-101",
                   revision_label="IFC")
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    v1 = doc["versions"][0]
    assert v1["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert v1["content_type"] == "application/pdf" and v1["scan_status"] == "not_scanned"
    assert v1["revision_label"] == "IFC" and doc["current_version_number"] == 1

    rev2 = PDF + b"% revision 2\n"
    v2 = owner.post(f"/api/v1/documents/{doc['id']}/versions", data={"revision_label": "Rev 2", "notes": "ASI-03"},
                    files={"file": ("A-101 rev2.pdf", io.BytesIO(rev2), "application/pdf")})
    assert v2.status_code == 201
    assert v2.json()["current_version_number"] == 2 and len(v2.json()["versions"]) == 2

    d1 = owner.get(f"/api/v1/documents/{doc['id']}/versions/1/download")
    d2 = owner.get(f"/api/v1/documents/{doc['id']}/versions/2/download")
    assert d1.content == PDF and d2.content == rev2
    assert d2.headers["content-type"] == "application/pdf"
    assert "attachment" in d2.headers["content-disposition"] and d2.headers["x-content-type-options"] == "nosniff"

    listing = owner.get(f"/api/v1/documents?project_id={project['id']}").json()
    assert listing["total"] == 1 and listing["items"][0]["current_version"]["version_number"] == 2
    assert owner.get("/api/v1/documents?q=A-101").json()["total"] == 1


def test_rejects_disallowed_and_spoofed_files(owner) -> None:  # type: ignore[no-untyped-def]
    assert _upload(owner, name="tool.exe", content=b"MZ" + b"\x00" * 50).json()["error"]["code"] == \
        "file_type_not_allowed"
    spoof = _upload(owner, name="plan.pdf", content=ELF)
    assert spoof.status_code == 422
    mismatch = _upload(owner, name="photo.pdf", content=PNG)
    assert mismatch.json()["error"]["code"] == "file_content_mismatch"
    assert _upload(owner, name="empty.pdf", content=b"").json()["error"]["code"] == "file_empty"
    big = _upload(owner, name="big.pdf", content=PDF + b"0" * (2 * 1024 * 1024 + 1))
    assert big.status_code == 413
    assert _upload(owner, category="memes").status_code == 422


def test_filename_is_sanitised(owner) -> None:  # type: ignore[no-untyped-def]
    resp = _upload(owner, name="../../etc/passwd\x00.pdf")
    assert resp.status_code == 201, resp.text
    name = resp.json()["versions"][0]["original_filename"]
    assert "/" not in name and ".." not in name.split("_")[0] and "\x00" not in name


def test_delete_is_soft_and_permissioned(owner) -> None:  # type: ignore[no-untyped-def]
    doc = _upload(owner).json()
    pm = invite_and_join(owner, "project_manager")
    assert pm.delete(f"/api/v1/documents/{doc['id']}").status_code == 403
    assert owner.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert owner.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    actions = [e["action"] for e in owner.get(f"/api/v1/audit-events?entity_id={doc['id']}").json()["items"]]
    assert actions == ["document.deleted", "document.uploaded"]


def test_project_documents_follow_project_visibility(owner) -> None:  # type: ignore[no-untyped-def]
    project = make_project(owner)
    doc = _upload(owner, project_id=project["id"]).json()
    org_doc = _upload(owner, title="Company Safety Manual", category="report").json()
    engineer = invite_and_join(owner, "field_engineer")
    assert engineer.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert engineer.get(f"/api/v1/documents/{org_doc['id']}").status_code == 200
    owner.post(f"/api/v1/projects/{project['id']}/members",
               json={"user_id": engineer.user_id, "project_role": "field_engineer"})
    assert engineer.get(f"/api/v1/documents/{doc['id']}/versions/1/download").status_code == 200


def test_metadata_update_audited(owner) -> None:  # type: ignore[no-untyped-def]
    doc = _upload(owner).json()
    upd = owner.patch(f"/api/v1/documents/{doc['id']}", json={"title": "Level 1 Plan (Revised)",
                                                               "discipline": "structural"})
    assert upd.status_code == 200 and upd.json()["discipline"] == "structural"
    events = owner.get(f"/api/v1/audit-events?entity_id={doc['id']}").json()["items"]
    assert events[0]["changes"]["title"]["to"] == "Level 1 Plan (Revised)"
