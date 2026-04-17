"""Tests for admin user management endpoints."""
from server_backend.conftest import (
    create_test_event, create_test_user, inject_session, _make_client,
)


# ── POST /admin/users (create user) ──


def test_create_user_happy_path(db, admin_client):
    """Admin can create a user with activation URL returned."""
    event, _ = create_test_event(db, name="Evt")
    r = admin_client.post("/api/v1/admin/users", json={
        "username": "new.user",
        "display_name": "New User",
        "email": "new@test.com",
        "event_id": event.id,
        "can_edit": True,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["username"] == "new.user"
    assert data["user"]["is_activated"] is False
    assert "/activate?token=" in data["activation_url"]


def test_create_user_duplicate_username(db, admin_client):
    """Creating a user with an existing username → 409."""
    event, _ = create_test_event(db, name="Evt")
    create_test_user(db, username="duplicate", event_id=event.id)
    r = admin_client.post("/api/v1/admin/users", json={
        "username": "duplicate",
        "display_name": "Dup",
        "event_id": event.id,
    })
    assert r.status_code == 409


def test_create_user_missing_event_id(db, admin_client):
    """Creating a user without event_id → 422."""
    r = admin_client.post("/api/v1/admin/users", json={
        "username": "noevt",
        "display_name": "No Event",
    })
    assert r.status_code == 422


def test_create_user_issuer_forces_own_event(db):
    """Issuer creating a user → event_id forced to issuer's event."""
    event, _ = create_test_event(db, name="IssuerEvt")
    other_event, _ = create_test_event(db, name="OtherEvt")
    issuer = create_test_user(
        db, username="iss_creator", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.post("/api/v1/admin/users", json={
        "username": "created_by_issuer",
        "display_name": "User By Issuer",
        "event_id": other_event.id,  # tries to set different event
    })
    assert r.status_code == 200
    data = r.json()
    # event_id forced to issuer's event
    assert data["user"]["event_id"] == event.id


def test_create_user_issuer_cannot_grant_admin(db):
    """Issuer cannot set is_admin on new users."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="iss_priv", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.post("/api/v1/admin/users", json={
        "username": "escalated",
        "display_name": "Escalated",
        "event_id": event.id,
        "is_admin": True,
    })
    assert r.status_code == 403


def test_create_user_issuer_cannot_grant_issuer(db):
    """Issuer cannot set is_issuer on new users."""
    event, _ = create_test_event(db, name="Evt")
    issuer = create_test_user(
        db, username="iss_priv2", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.post("/api/v1/admin/users", json={
        "username": "escalated2",
        "display_name": "Escalated2",
        "event_id": event.id,
        "is_issuer": True,
    })
    assert r.status_code == 403


def test_only_root_can_set_issuer(db, admin_client):
    """Non-root admin cannot grant issuer role."""
    event, _ = create_test_event(db, name="Evt")
    r = admin_client.post("/api/v1/admin/users", json={
        "username": "want_issuer",
        "display_name": "Want Issuer",
        "event_id": event.id,
        "is_issuer": True,
    })
    assert r.status_code == 403


def test_root_can_set_issuer(db, root_client):
    """Root admin can grant issuer role."""
    event, _ = create_test_event(db, name="Evt")
    r = root_client.post("/api/v1/admin/users", json={
        "username": "new_issuer",
        "display_name": "New Issuer",
        "event_id": event.id,
        "is_issuer": True,
    })
    assert r.status_code == 200
    assert r.json()["user"]["is_issuer"] is True


# ── GET /admin/users ──


def test_list_users_admin_sees_all(db, root_client):
    """Admin can see all non-root users."""
    event, _ = create_test_event(db, name="Evt")
    create_test_user(db, username="u1", event_id=event.id)
    create_test_user(db, username="u2", event_id=event.id)

    r = root_client.get("/api/v1/admin/users")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "u1" in usernames
    assert "u2" in usernames


def test_list_users_issuer_sees_own_event_only(db):
    """Issuer only sees users from their own event."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    create_test_user(db, username="u_e1", event_id=event1.id)
    create_test_user(db, username="u_e2", event_id=event2.id)

    issuer = create_test_user(
        db, username="iss_list", is_issuer=True, event_id=event1.id,
    )
    client = _make_client(db, issuer)

    r = client.get("/api/v1/admin/users")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "u_e1" in usernames
    assert "u_e2" not in usernames


# ── PUT /admin/users/{id} ──


def test_update_user_fields(db, admin_client):
    """Admin can update user fields."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="updatable", event_id=event.id)

    r = admin_client.put(f"/api/v1/admin/users/{user.id}", json={
        "display_name": "Updated Name",
        "can_edit": True,
        "tags": ["tag1", "tag2"],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Updated Name"
    assert data["can_edit"] is True
    assert data["tags"] == ["tag1", "tag2"]


def test_update_user_issuer_blocked_from_privilege_escalation(db):
    """Issuer cannot change is_admin or is_issuer on users."""
    event, _ = create_test_event(db, name="Evt")
    target = create_test_user(db, username="target_esc", event_id=event.id)
    issuer = create_test_user(
        db, username="iss_esc", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.put(f"/api/v1/admin/users/{target.id}", json={
        "is_admin": True,
    })
    assert r.status_code == 403

    r2 = client.put(f"/api/v1/admin/users/{target.id}", json={
        "is_issuer": True,
    })
    assert r2.status_code == 403


def test_update_user_issuer_blocked_event_reassignment(db):
    """Issuer cannot reassign user to another event."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    target = create_test_user(db, username="target_ev", event_id=event1.id)
    issuer = create_test_user(
        db, username="iss_ev", is_issuer=True, event_id=event1.id,
    )
    client = _make_client(db, issuer)

    r = client.put(f"/api/v1/admin/users/{target.id}", json={
        "event_id": event2.id,
    })
    assert r.status_code == 403


def test_update_user_cannot_modify_root(db, admin_client):
    """Cannot modify root admin user."""
    from app.models.user import User
    root = db.query(User).filter(User.username == "root.admin").first()
    r = admin_client.put(f"/api/v1/admin/users/{root.id}", json={
        "display_name": "Hacked",
    })
    assert r.status_code == 403


def test_update_issuer_cross_event_blocked(db):
    """Issuer cannot update user from a different event."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    target = create_test_user(db, username="other_evt", event_id=event2.id)
    issuer = create_test_user(
        db, username="iss_cross", is_issuer=True, event_id=event1.id,
    )
    client = _make_client(db, issuer)

    r = client.put(f"/api/v1/admin/users/{target.id}", json={
        "display_name": "Should Fail",
    })
    assert r.status_code == 403


# ── DELETE /admin/users/{id} ──


def test_delete_user_requires_reauth(db, admin_client):
    """Deleting a user requires re-authentication."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="to_delete", event_id=event.id)
    r = admin_client.delete(f"/api/v1/admin/users/{user.id}")
    assert r.status_code == 403
    assert "Re-authentication required" in r.json().get("detail", "")


def test_delete_user_with_reauth(db, reauth_admin_client):
    """Admin with reauth can delete a user."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(db, username="to_delete2", event_id=event.id)
    r = reauth_admin_client.delete(f"/api/v1/admin/users/{user.id}")
    assert r.status_code == 200


def test_delete_root_admin_blocked(db, reauth_admin_client):
    """Cannot delete root admin."""
    from app.models.user import User
    root = db.query(User).filter(User.username == "root.admin").first()
    if not root:
        root = create_test_user(
            db, username="root.admin", is_root_admin=True, is_admin=True,
        )
    r = reauth_admin_client.delete(f"/api/v1/admin/users/{root.id}")
    assert r.status_code == 403
