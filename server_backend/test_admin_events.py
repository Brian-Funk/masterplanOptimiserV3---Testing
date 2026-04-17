"""Tests for admin event endpoints."""
from server_backend.conftest import (
    create_test_event, create_test_user, _make_client,
)


# ── POST /admin/events ──


def test_create_event(db, admin_client):
    """Admin can create an event; publish secret returned once."""
    r = admin_client.post("/api/v1/admin/events", json={
        "name": "New Event",
        "location": "Zurich",
        "start_date": "2026-08-01",
        "end_date": "2026-08-10",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["event"]["name"] == "New Event"
    assert "publish_secret" in data
    assert len(data["publish_secret"]) > 20


def test_create_event_minimal(db, admin_client):
    """Event can be created with just a name."""
    r = admin_client.post("/api/v1/admin/events", json={
        "name": "Minimal Event",
    })
    assert r.status_code == 200
    assert r.json()["event"]["name"] == "Minimal Event"


# ── GET /admin/events ──


def test_list_events(db, admin_client):
    """Admin can list all events."""
    create_test_event(db, name="Event A")
    create_test_event(db, name="Event B")

    r = admin_client.get("/api/v1/admin/events")
    assert r.status_code == 200
    names = [e["name"] for e in r.json()]
    assert "Event A" in names
    assert "Event B" in names


# ── Issuer cannot access event endpoints ──


def test_issuer_cannot_create_event(db):
    """Issuers are blocked from event creation (require_admin)."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="iss_evt", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.post("/api/v1/admin/events", json={
        "name": "Should Fail",
    })
    assert r.status_code == 403


def test_issuer_cannot_list_events(db):
    """Issuers are blocked from listing events."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="iss_list_evt", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.get("/api/v1/admin/events")
    assert r.status_code == 403


# ── DELETE /admin/events/{id} ──


def test_delete_event_requires_reauth(db, admin_client):
    """Event deletion requires re-authentication."""
    event, _ = create_test_event(db, name="To Delete")
    r = admin_client.delete(f"/api/v1/admin/events/{event.id}")
    assert r.status_code == 403


def test_delete_event_cascade(db, reauth_admin_client):
    """Deleting an event cascades to users and published data."""
    event, _ = create_test_event(db, name="Cascade Evt")
    user = create_test_user(db, username="evt_user", event_id=event.id)

    r = reauth_admin_client.delete(f"/api/v1/admin/events/{event.id}")
    assert r.status_code == 200
    assert "deleted" in r.json()["message"].lower()

    # Verify user is gone
    from app.models.user import User
    remaining = db.query(User).filter(User.id == user.id).first()
    assert remaining is None


def test_delete_event_not_found(db, reauth_admin_client):
    """Deleting non-existent event → 404."""
    r = reauth_admin_client.delete("/api/v1/admin/events/99999")
    assert r.status_code == 404


# ── POST /admin/events/{id}/regenerate-secret ──


def test_regenerate_secret(db, reauth_admin_client):
    """Admin with reauth can regenerate an event's publish secret."""
    event, old_secret = create_test_event(db, name="Regen Evt")
    r = reauth_admin_client.post(f"/api/v1/admin/events/{event.id}/regenerate-secret")
    assert r.status_code == 200
    new_secret = r.json()["publish_secret"]
    assert new_secret != old_secret
    assert len(new_secret) > 20
