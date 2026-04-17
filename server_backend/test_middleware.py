"""Tests for CSRF enforcement and content-type middleware."""
from server_backend.conftest import (
    create_test_event, create_test_user, inject_session, _make_client,
)

from httpx import ASGITransport, Client


def test_csrf_required_on_write(db):
    """POST to cookie-authenticated endpoint without CSRF → 403."""
    from app.main import app

    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="csrf_user", is_admin=True, event_id=event.id,
    )
    raw_token, csrf = inject_session(db, user)

    # Client with session cookie but WITHOUT X-CSRF-Token header
    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        cookies={"session_id": raw_token, "csrf_token": csrf},
        headers={"Content-Type": "application/json"},
        # Note: no X-CSRF-Token header
    )

    r = client.post("/api/v1/admin/events", json={"name": "CSRF Test"})
    assert r.status_code == 403
    assert "CSRF" in r.json().get("detail", "")


def test_csrf_not_required_on_get(db, admin_client):
    """GET requests don't need CSRF tokens."""
    r = admin_client.get("/api/v1/admin/events")
    assert r.status_code == 200


def test_content_type_enforcement(db):
    """POST to API without application/json content-type → 415."""
    from app.main import app

    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="ct_user", is_admin=True, event_id=event.id,
    )
    raw_token, csrf = inject_session(db, user)

    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        cookies={"session_id": raw_token, "csrf_token": csrf},
        headers={
            "X-CSRF-Token": csrf,
            "Content-Type": "text/plain",  # wrong content type
        },
    )

    r = client.post("/api/v1/admin/events", content='{"name": "CT Test"}')
    assert r.status_code == 415


def test_body_size_limit(db):
    """Request exceeding body size limit → 413."""
    from app.main import app

    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(10 * 1024 * 1024),  # 10MB
        },
    )

    r = client.post("/api/v1/admin/events", content=b"x" * 100)
    assert r.status_code == 413


def test_publish_exempt_from_csrf(db):
    """Publish endpoint uses Bearer token, not CSRF."""
    event, secret = create_test_event(db, name="Evt")
    from app.main import app

    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )

    r = client.post("/api/v1/publish/publish", json={
        "tasks": [],
        "persons": [],
    })
    assert r.status_code == 200


def test_health_check(db):
    """Health endpoint returns ok."""
    from app.main import app

    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
    )
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")
