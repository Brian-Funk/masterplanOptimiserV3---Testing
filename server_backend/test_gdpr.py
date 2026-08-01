"""Tests for GDPR endpoints - data export, deletion request, anonymisation."""
from server_backend.conftest import (
    create_test_event, create_test_user, _make_client, inject_session,
)


# ── GET /admin/users/{id}/export ──


def test_gdpr_export(db, reauth_admin_client):
    """A recently re-authenticated admin can export user data."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="exportme", event_id=event.id)

    r = reauth_admin_client.get(f"/api/v1/admin/users/{user.id}/export")
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["username"] == "exportme"
    assert "sessions_count" in data
    assert "credentials_count" in data


def test_gdpr_export_not_found(db, reauth_admin_client):
    """Export for non-existent user → 404."""
    r = reauth_admin_client.get("/api/v1/admin/users/99999/export")
    assert r.status_code == 404


def test_gdpr_export_regular_user_blocked(db):
    """Regular users cannot access GDPR export."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="noexport", event_id=event.id)
    client = _make_client(db, user)

    r = client.get(f"/api/v1/admin/users/{user.id}/export")
    assert r.status_code == 403


def test_gdpr_export_requires_reauthentication(db, admin_client):
    """An ordinary admin session cannot export personal data without step-up."""
    event, _ = create_test_event(db, name="Export Reauth")
    user = create_test_user(db, username="export.reauth", event_id=event.id)

    response = admin_client.get(f"/api/v1/admin/users/{user.id}/export")

    assert response.status_code == 403
    assert "Re-authentication required" in response.json()["detail"]


# ── DELETE /admin/users/{id}/gdpr-delete (anonymise) ──


def test_gdpr_anonymise_server_only_user_is_ready_for_live_purge(db, reauth_admin_client):
    """A server-only account skips the inapplicable desktop work order."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="anonme", event_id=event.id)

    r = reauth_admin_client.delete(f"/api/v1/admin/users/{user.id}/gdpr-delete")
    assert r.status_code == 200
    assert r.json()["state"] == "ready_for_live_purge"
    assert "server-only account" in r.json()["message"].lower()

    # Verify anonymisation
    from app.models.user import User
    retained = db.query(User).filter(User.id == user.id).one()
    assert retained.username == "anonme"
    assert retained.is_active is False


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
    client = _make_client(db, user, reauth=True)

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


def test_dismiss_deletion_request(db, reauth_admin_client):
    """Admin can dismiss a pending deletion request."""
    from datetime import datetime, timezone
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="dismiss_target", event_id=event.id)
    client = _make_client(db, user, reauth=True)
    client.post("/api/v1/user/request-deletion")

    r = reauth_admin_client.delete(f"/api/v1/admin/users/{user.id}/deletion-request")
    assert r.status_code == 200

    # Verify flag cleared
    from app.models.user import User
    updated = db.query(User).filter(User.id == user.id).first()
    assert updated.deletion_requested_at is None


def test_dismiss_no_pending_request(db, reauth_admin_client):
    """Dismissing when no request is pending → 409."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="no_request", event_id=event.id)

    r = reauth_admin_client.delete(f"/api/v1/admin/users/{user.id}/deletion-request")
    assert r.status_code == 409
