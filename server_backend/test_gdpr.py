"""Tests for GDPR endpoints — data export, deletion request, anonymisation."""
from server_backend.conftest import (
    create_test_event, create_test_user, _make_client, inject_session,
)


# ── GET /admin/users/{id}/export ──


def test_gdpr_export(db, admin_client):
    """Admin can export user data."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="exportme", event_id=event.id)

    r = admin_client.get(f"/api/v1/admin/users/{user.id}/export")
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["username"] == "exportme"
    assert "sessions_count" in data
    assert "credentials_count" in data


def test_gdpr_export_not_found(db, admin_client):
    """Export for non-existent user → 404."""
    r = admin_client.get("/api/v1/admin/users/99999/export")
    assert r.status_code == 404


def test_gdpr_export_regular_user_blocked(db):
    """Regular users cannot access GDPR export."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="noexport", event_id=event.id)
    client = _make_client(db, user)

    r = client.get(f"/api/v1/admin/users/{user.id}/export")
    assert r.status_code == 403


# ── DELETE /admin/users/{id}/gdpr-delete (anonymise) ──


def test_gdpr_anonymise(db, reauth_admin_client):
    """Admin with reauth can anonymise a user."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="anonme", event_id=event.id)

    r = reauth_admin_client.delete(f"/api/v1/admin/users/{user.id}/gdpr-delete")
    assert r.status_code == 200
    assert "anonymised" in r.json()["message"].lower()

    # Verify anonymisation
    from app.models.user import User
    anon = db.query(User).filter(User.id == user.id).first()
    assert anon.username == f"deleted_{user.id}"
    assert anon.display_name == "Deleted User"
    assert anon.email is None
    assert anon.is_active is False


def test_gdpr_anonymise_root_blocked(db, reauth_admin_client):
    """Cannot anonymise root admin."""
    from app.models.user import User
    root = db.query(User).filter(User.username == "root.admin").first()
    if not root:
        root = create_test_user(
            db, username="root.admin", is_root_admin=True, is_admin=True,
        )

    r = reauth_admin_client.delete(f"/api/v1/admin/users/{root.id}/gdpr-delete")
    assert r.status_code == 403


# ── POST /user/request-deletion ──


def test_user_request_deletion(db):
    """User can request their own deletion."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="deleteme", event_id=event.id)
    client = _make_client(db, user)

    r = client.post("/api/v1/user/request-deletion")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Verify flag is set
    from app.models.user import User
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.deletion_requested_at is not None


def test_root_cannot_request_self_deletion(db, root_client):
    """Root admin cannot request self-deletion."""
    r = root_client.post("/api/v1/user/request-deletion")
    assert r.status_code == 403


# ── DELETE /admin/users/{id}/deletion-request (dismiss) ──


def test_dismiss_deletion_request(db, admin_client):
    """Admin can dismiss a pending deletion request."""
    from datetime import datetime, timezone
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="dismiss_target", event_id=event.id)
    user.deletion_requested_at = datetime.now(timezone.utc)
    db.commit()

    r = admin_client.delete(f"/api/v1/admin/users/{user.id}/deletion-request")
    assert r.status_code == 200

    # Verify flag cleared
    from app.models.user import User
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.deletion_requested_at is None


def test_dismiss_no_pending_request(db, admin_client):
    """Dismissing when no request is pending → 409."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="no_request", event_id=event.id)

    r = admin_client.delete(f"/api/v1/admin/users/{user.id}/deletion-request")
    assert r.status_code == 409
