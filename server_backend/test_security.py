"""Tests for authentication and role-based access control."""
from server_backend.conftest import (
    create_test_event, create_test_user, inject_session, _make_client,
)

from httpx import ASGITransport, Client


# ── /api/v1/auth/me ──


def test_me_returns_401_without_cookie(db):
    """GET /me without session cookie → 401."""
    from app.main import app
    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
    )
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_user_with_valid_session(db, root_client):
    """GET /me with valid session → user data."""
    r = root_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "root.admin"
    assert data["is_root_admin"] is True


def test_me_returns_issuer_fields(db):
    """GET /me returns is_issuer field for issuer users."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="iss", display_name="Issuer",
        is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, user)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["is_issuer"] is True
    assert data["event_id"] == event.id


def test_me_returns_401_with_expired_session(db):
    """GET /me with expired session → 401."""
    from datetime import datetime, timedelta, timezone
    from app.main import app
    from app.models.user import AuthSession
    from app.core.sessions import _hash_token
    import secrets

    event, _ = create_test_event(db, name="Exp")
    user = create_test_user(db, username="expired_user", event_id=event.id)

    raw_token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session = AuthSession(
        user_id=user.id,
        session_token=_hash_token(raw_token),
        csrf_token=csrf,
        expires_at=now - timedelta(hours=1),  # already expired
        last_seen_at=now - timedelta(hours=2),
    )
    db.add(session)
    db.commit()

    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        cookies={"session_id": raw_token, "csrf_token": csrf},
    )
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


# ── require_admin ──


def test_admin_endpoint_blocks_regular_user(db):
    """Admin-only endpoint returns 403 for regular users."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="nonadmin", event_id=event.id)
    client = _make_client(db, user)
    r = client.get("/api/v1/admin/events")
    assert r.status_code == 403


def test_admin_endpoint_allows_admin(db, admin_client):
    """Admin-only endpoint returns 200 for admins."""
    r = admin_client.get("/api/v1/admin/events")
    assert r.status_code == 200


# ── require_admin_or_issuer ──


def test_admin_or_issuer_allows_issuer(db):
    """Endpoints with require_admin_or_issuer allow issuers."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="issuer1", display_name="Iss",
        is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 200


def test_admin_or_issuer_blocks_regular_user(db):
    """Endpoints with require_admin_or_issuer block regular users."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="regular", event_id=event.id)
    client = _make_client(db, user)
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 403


# ── _is_issuer_only ──


def test_is_issuer_only_true_for_pure_issuer():
    """_is_issuer_only returns True for issuer without admin."""
    from app.core.security import _is_issuer_only
    from unittest.mock import MagicMock
    user = MagicMock()
    user.is_issuer = True
    user.is_admin = False
    user.is_root_admin = False
    assert _is_issuer_only(user) is True


def test_is_issuer_only_false_for_admin_plus_issuer():
    """_is_issuer_only returns False when user is both admin and issuer."""
    from app.core.security import _is_issuer_only
    from unittest.mock import MagicMock
    user = MagicMock()
    user.is_issuer = True
    user.is_admin = True
    user.is_root_admin = False
    assert _is_issuer_only(user) is False


# ── require_same_event ──


def test_require_same_event_blocks_cross_event(db):
    """Issuer cannot access users from a different event."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    issuer = create_test_user(
        db, username="iss_e1", display_name="Iss",
        is_issuer=True, event_id=event1.id,
    )
    target = create_test_user(
        db, username="target_e2", display_name="Target",
        event_id=event2.id,
    )
    from app.core.security import require_same_event
    from fastapi import HTTPException
    import pytest as pt
    with pt.raises(HTTPException) as exc_info:
        require_same_event(target, issuer)
    assert exc_info.value.status_code == 403


def test_require_same_event_allows_same_event(db):
    """Issuer can access users from the same event."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="iss", is_issuer=True, event_id=event.id,
    )
    target = create_test_user(
        db, username="tgt", event_id=event.id,
    )
    from app.core.security import require_same_event
    # Should not raise
    require_same_event(target, issuer)


def test_require_same_event_noop_for_admin(db):
    """require_same_event is a no-op for full admins."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    admin = create_test_user(
        db, username="adm", is_admin=True, event_id=event1.id,
    )
    target = create_test_user(
        db, username="tgt", event_id=event2.id,
    )
    from app.core.security import require_same_event
    # Should not raise
    require_same_event(target, admin)


# ── require_recent_reauth ──


def test_reauth_required_blocks_without_reauth(db, admin_client):
    """Destructive endpoint requires re-authentication."""
    # admin_client does not have reauth_at set
    # Try to delete an event — requires require_recent_reauth
    r = admin_client.delete("/api/v1/admin/events/9999")
    assert r.status_code == 403
    assert "Re-authentication required" in r.json().get("detail", "")


def test_reauth_required_allows_with_reauth(db, reauth_admin_client):
    """Destructive endpoint succeeds with fresh re-authentication."""
    # Event doesn't exist → 404, but the auth check passes
    r = reauth_admin_client.delete("/api/v1/admin/events/9999")
    assert r.status_code == 404  # past the auth check


# ── Logout ──


def test_logout_clears_session(db, admin_client):
    """POST /logout clears session."""
    r = admin_client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # Subsequent /me should fail
    r2 = admin_client.get("/api/v1/auth/me")
    assert r2.status_code == 401
