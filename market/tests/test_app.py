from __future__ import annotations

import io
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.main import app
from backend.repositories import sends_repo
from backend.security import decrypt_secret

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PASSWORD = "password123"


def register(email: str) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def wait_run(client: TestClient, run_id: str) -> dict:
    last = {}
    for _ in range(100):
        last = client.get(f"/api/sends/runs/{run_id}").json()
        if last["status"] == "done":
            return last
        time.sleep(0.02)
    raise AssertionError(last)


def test_accounts_are_isolated():
    ada = register("ada@example.com")
    grace = register("grace@example.com")
    germany = ada.post("/api/countries", json={"label": "Germany", "location_line": "Berlin", "phone": "+49"}).json()
    ada.put("/api/profile", json={"name": "Ada Lovelace", "headline": "Analyst"})
    ada.post(
        "/api/profile/resume",
        files={"file": ("ada.pdf", PDF, "application/pdf")},
    )
    job = ada.post(
        "/api/jobs",
        json={
            "company": "Acme",
            "role": "Analyst",
            "contact_email": "hr@acme.example",
            "job_description": "Study the books",
            "country_id": germany["id"],
        },
    ).json()

    assert grace.get("/api/jobs").json() == []
    assert grace.get("/api/countries").json() == []
    assert grace.get("/api/profile").json()["name"] == ""
    assert grace.get("/api/stats").json()["total_attempts"] == 0
    assert grace.delete(f"/api/jobs/{job['id']}").status_code == 400
    assert grace.get("/api/resumes/base").status_code == 404
    assert ada.get("/api/resumes/base").status_code == 200
    assert ada.get("/api/jobs").json()[0]["id"] == job["id"]


def test_login_logout_and_duplicate_email():
    client = register("login@example.com")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    wrong = client.post("/api/auth/login", json={"email": "login@example.com", "password": "wrong-password"})
    assert wrong.status_code == 401
    assert client.post("/api/auth/login", json={"email": "login@example.com", "password": PASSWORD}).status_code == 200
    again = client.post("/api/auth/register", json={"email": "login@example.com", "password": PASSWORD})
    assert again.status_code == 400


def test_mailbox_password_is_not_returned():
    client = register("mail@example.com")
    secret = "super-secret-app"
    saved = client.put(
        "/api/mailbox",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "mail@example.com",
            "from_name": "Mail User",
            "from_email": "mail@example.com",
            "password": secret,
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["password_set"] is True
    assert secret not in saved.text
    assert "password_encrypted" not in body
    user_id = client.get("/api/auth/me").json()["id"]
    with connect() as conn:
        row = conn.execute("SELECT password_encrypted FROM mailboxes WHERE user_id = ?", (user_id,)).fetchone()
    assert secret not in row["password_encrypted"]
    assert decrypt_secret(row["password_encrypted"]) == secret
    kept = client.put(
        "/api/mailbox",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "mail@example.com",
            "from_name": "Mail User",
            "from_email": "mail@example.com",
            "password": "",
        },
    )
    assert kept.status_code == 200
    with connect() as conn:
        again = conn.execute("SELECT password_encrypted FROM mailboxes WHERE user_id = ?", (user_id,)).fetchone()
    assert decrypt_secret(again["password_encrypted"]) == secret


def test_spreadsheet_import_matches_country_labels():
    client = register("sheet@example.com")
    germany = client.post("/api/countries", json={"label": "Germany", "location_line": "Berlin", "phone": ""}).json()
    remote = client.post("/api/countries", json={"label": "Remote", "location_line": "Remote", "phone": ""}).json()
    buffer = io.BytesIO()
    pd.DataFrame(
        [
            {"Company name": "Northwind", "Role": "Accountant", "HR email": "jobs@northwind.example", "Country": "Germany"},
            {"Company name": "Contoso", "Role": "Nurse", "HR email": "jobs@contoso.example", "Country": "Remote"},
            {"Company name": "Bad Row", "Role": "Nurse", "HR email": "not-an-email", "Country": "Germany"},
        ]
    ).to_excel(buffer, index=False)
    response = client.post(
        "/api/jobs/upload",
        files={"file": ("jobs.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"country_id": germany["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 2
    assert response.json()["skipped"]
    jobs = {job["company"]: job for job in client.get("/api/jobs").json()}
    assert jobs["Northwind"]["country_id"] == germany["id"]
    assert jobs["Contoso"]["country_id"] == remote["id"]


def test_preview_dry_run_dedup_and_daily_cap(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "backend.services.preview_service.ai_service.write_email",
        lambda **_kwargs: {"subject": "Application for Analyst", "body": "Hello, I am applying with the experience on my profile."},
    )
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append({"to": kwargs["to_email"], "subject": kwargs["subject"]})

    monkeypatch.setattr("backend.services.email_service.send_message", fake_send)
    monkeypatch.setenv("DAILY_SEND_CAP", "1")

    client = register("send@example.com")
    country = client.post("/api/countries", json={"label": "Kenya", "location_line": "Nairobi", "phone": "+254"}).json()
    client.put("/api/profile", json={"name": "Grace Hopper", "headline": "Analyst", "summary": "Built compilers."})
    client.post("/api/profile/resume", files={"file": ("grace.pdf", PDF, "application/pdf")})
    client.put(
        "/api/mailbox",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "grace@example.com",
            "from_name": "Grace",
            "from_email": "grace@example.com",
            "password": "app-password-value",
        },
    )
    job = client.post(
        "/api/jobs",
        json={
            "company": "Navy",
            "role": "Analyst",
            "contact_email": "hr@navy.example",
            "country_id": country["id"],
            "job_description": "Compilers",
        },
    ).json()
    preview = client.post(
        "/api/jobs/preview",
        json={"job_ids": [job["id"]], "country_id": country["id"], "resume_mode": "base"},
    )
    assert preview.status_code == 200, preview.text
    item = preview.json()[0]
    assert item["subject"]
    assert item["error"] == ""

    payload = {
        "dry_run": True,
        "items": [
            {
                "job_id": job["id"],
                "subject": item["subject"],
                "body": item["body"],
                "resume_mode": "base",
                "country_id": country["id"],
            }
        ],
    }
    dry = wait_run(client, client.post("/api/sends", json=payload).json()["id"])
    assert dry["dry_runs"] == 1
    assert calls == []

    payload["dry_run"] = False
    first = wait_run(client, client.post("/api/sends", json=payload).json()["id"])
    assert first["sent"] == 1
    assert calls[0]["to"] == "hr@navy.example"

    second = wait_run(client, client.post("/api/sends", json=payload).json()["id"])
    assert second["skipped"] == 1
    assert len(calls) == 1

    sends_repo.record(
        client.get("/api/auth/me").json()["id"],
        job_id=None,
        company="Other",
        role="Analyst",
        contact_email="other@example.com",
        country_label="Kenya",
        status="sent",
        subject="x",
        body="y",
        resume_filename="",
        error="",
    )
    other = client.post(
        "/api/jobs",
        json={"company": "Other Co", "role": "Writer", "contact_email": "writer@example.com", "country_id": country["id"]},
    ).json()
    capped = wait_run(
        client,
        client.post(
            "/api/sends",
            json={
                "dry_run": False,
                "items": [
                    {
                        "job_id": other["id"],
                        "subject": "Hello",
                        "body": "I am applying.",
                        "resume_mode": "base",
                        "country_id": country["id"],
                    }
                ],
            },
        ).json()["id"],
    )
    assert capped["results"][0]["status"] == "failed"
    assert "Daily cap" in capped["results"][0]["error"]
    assert len(calls) == 1

    other_user = register("other@example.com")
    assert other_user.get("/api/sends").json() == []
    assert other_user.get("/api/stats").json()["sent"] == 0


def test_one_default_resume_per_country():
    ada = register("resumes@example.com")
    germany = ada.post("/api/countries", json={"label": "Germany", "location_line": "Berlin", "phone": ""}).json()
    first = ada.post(
        "/api/resumes",
        data={"country_id": germany["id"]},
        files={"file": ("berlin.pdf", PDF, "application/pdf")},
    )
    assert first.status_code == 200, first.text
    second = ada.post(
        "/api/resumes",
        data={"country_id": germany["id"]},
        files={"file": ("other.pdf", PDF, "application/pdf")},
    )
    assert second.status_code == 200, second.text
    listed = ada.get("/api/resumes").json()
    defaults = [item for item in listed if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == first.json()["id"]
    changed = ada.post(f"/api/resumes/{second.json()['id']}/default")
    assert changed.status_code == 200
    assert changed.json()["is_default"] is True
    listed = ada.get("/api/resumes").json()
    defaults = [item for item in listed if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == second.json()["id"]
    grace = register("resume-other@example.com")
    assert grace.get("/api/resumes").json() == []
    assert grace.get(f"/api/resumes/file/{first.json()['id']}").status_code == 404
    assert ada.get(f"/api/resumes/file/{second.json()['id']}").status_code == 200


def test_sheet_requires_email_and_allows_a_blank_role():
    client = register("cold@example.com")
    germany = client.post("/api/countries", json={"label": "Germany", "location_line": "Berlin", "phone": ""}).json()
    uploaded = client.post(
        "/api/resumes",
        data={"country_id": germany["id"]},
        files={"file": ("default.pdf", PDF, "application/pdf")},
    ).json()
    missing = io.BytesIO()
    pd.DataFrame([{"Company": "Acme", "Role": "Nurse"}]).to_excel(missing, index=False)
    rejected = client.post(
        "/api/jobs/upload",
        files={"file": ("jobs.xlsx", missing.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"country_id": germany["id"]},
    )
    assert rejected.status_code == 400
    assert "email" in rejected.json()["detail"].lower()

    buffer = io.BytesIO()
    pd.DataFrame(
        [
            {"Email": "hr@acme.example", "Skills": "SQL"},
            {"Email": "not-an-email", "Company name": "Skip"},
            {"Company name": "Northwind", "Email": "jobs@northwind.example", "Job description": "Books"},
        ]
    ).to_excel(buffer, index=False)
    response = client.post(
        "/api/jobs/upload",
        files={"file": ("jobs.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"country_id": germany["id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert body["skipped"]
    jobs = {job["contact_email"]: job for job in client.get("/api/jobs").json()}
    assert jobs["hr@acme.example"]["role"] == ""
    assert jobs["hr@acme.example"]["skills"] == "SQL"
    assert jobs["hr@acme.example"]["resume_id"] == uploaded["id"]
    assert jobs["jobs@northwind.example"]["company"] == "Northwind"
    assert jobs["jobs@northwind.example"]["role"] == ""
    assert "Email" in body["columns"]
    assert "Skills" in body["columns"]


def test_a_new_spreadsheet_replaces_the_previous_columns():
    from openpyxl import Workbook

    client = register("replace-sheet@example.com")
    first = io.BytesIO()
    pd.DataFrame([{"Company": "Old Co", "Role": "Old role", "Email": "old@example.com", "Skills": "Old skill"}]).to_excel(first, index=False)
    uploaded = client.post(
        "/api/jobs/upload",
        files={"file": ("old.xlsx", first.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"country_id": ""},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["columns"] == ["Company", "Role", "Email", "Skills"]

    book = Workbook()
    old_sheet = book.active
    old_sheet.title = "Old"
    old_sheet.append(["Company", "Role", "Email", "Skills"])
    old_sheet.append(["Old Co", "Old role", "old@example.com", "Old skill"])
    new_sheet = book.create_sheet("New")
    new_sheet.append(["Email", "Company name"])
    new_sheet.append(["new@example.com", "New Co"])
    book.active = new_sheet
    second = io.BytesIO()
    book.save(second)
    replaced = client.post(
        "/api/jobs/upload",
        files={"file": ("new.xlsx", second.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"country_id": ""},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["columns"] == ["Email", "Company name"]
    jobs = client.get("/api/jobs").json()
    assert [job["contact_email"] for job in jobs] == ["new@example.com"]
    assert jobs[0]["skills"] == ""
    assert jobs[0]["role"] == ""


def test_gmail_address_is_not_used_as_the_host():
    client = register("gmail-box@example.com")
    saved = client.put(
        "/api/mailbox",
        json={
            "host": "person@gmail.com",
            "port": 587,
            "username": "rider",
            "from_name": "Razeen",
            "from_email": "person@gmail.com",
            "password": "abcd efgh ijkl mnop",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["host"] == "smtp.gmail.com"
    assert body["username"] == "person@gmail.com"
    assert "abcd efgh" not in saved.text
    user_id = client.get("/api/auth/me").json()["id"]
    with connect() as conn:
        row = conn.execute("SELECT password_encrypted FROM mailboxes WHERE user_id = ?", (user_id,)).fetchone()
    assert decrypt_secret(row["password_encrypted"]) == "abcdefghijklmnop"


def _docx(lines: list[str]) -> bytes:
    from docx import Document

    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_document_fills_profile_fields(monkeypatch: pytest.MonkeyPatch):
    client = register("import@example.com")
    monkeypatch.setattr(
        "backend.services.profile_import_service.ai_service.extract_profile",
        lambda _text: {
            "name": "Ada Lovelace",
            "headline": "Analyst",
            "email": "ada.import@example.com",
            "skills": [{"group": "Data", "items": "SQL"}],
            "experience": [{"title": "Analyst", "company": "Analytical Engines", "dates": "1843", "bullets": ["Wrote notes"]}],
        },
    )
    filled = client.post(
        "/api/profile/import",
        files={"file": ("ada.docx", _docx(["Ada Lovelace", "ada.import@example.com"]), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert filled.status_code == 200, filled.text
    body = filled.json()
    assert body["filled_by"] == "model"
    assert body["name"] == "Ada Lovelace"
    assert body["skills"][0]["items"] == "SQL"
    assert client.get("/api/profile").json()["name"] == ""

    def offline(_text):
        raise ValueError("Ollama is not reachable.")

    monkeypatch.setattr("backend.services.profile_import_service.ai_service.extract_profile", offline)
    fallback = client.post(
        "/api/profile/import",
        files={"file": ("ada.docx", _docx(["Ada Lovelace", "ada.import@example.com"]), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["filled_by"] == "text"
    assert fallback.json()["email"] == "ada.import@example.com"
    assert fallback.json()["name"] == "Ada Lovelace"
