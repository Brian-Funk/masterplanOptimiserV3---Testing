"""Tests for activation link endpoints."""
from server_backend.conftest import (
    create_test_event, create_test_user, _make_client, inject_session,
)


# ── POST /admin/users/{id}/activation-link ──


def test_create_activation_link(db, admin_client):
    """Admin can create an activation link for a user."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="needs_link", event_id=event.id, is_activated=False,
    )

    r = admin_client.post(f"/api/v1/admin/users/{user.id}/activation-link")
    assert r.status_code == 200
    assert "/activate?token=" in r.json()["activation_url"]


def test_create_activation_link_not_found(db, admin_client):
    """Activation link for non-existent user → 404."""
    r = admin_client.post("/api/v1/admin/users/99999/activation-link")
    assert r.status_code == 404


def test_create_activation_link_issuer_scoped(db):
    """Issuer can create link for user in same event only."""
    event, _ = create_test_event(db, name="Evt")
    other_event, _ = create_test_event(db, name="Other")
    user_same = create_test_user(
        db, username="same_evt", event_id=event.id, is_activated=False,
    )
    user_other = create_test_user(
        db, username="other_evt", event_id=other_event.id, is_activated=False,
    )
    issuer = create_test_user(
        db, username="iss_link", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    # Same event → OK
    r1 = client.post(f"/api/v1/admin/users/{user_same.id}/activation-link")
    assert r1.status_code == 200

    # Different event → 403
    r2 = client.post(f"/api/v1/admin/users/{user_other.id}/activation-link")
    assert r2.status_code == 403


# ── GET /admin/users/{id}/activation-links ──


def test_get_activation_link_status(db, admin_client):
    """Admin can get activation link status for a user."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="link_status", event_id=event.id, is_activated=False,
    )
    # Create a link first
    admin_client.post(f"/api/v1/admin/users/{user.id}/activation-link")

    r = admin_client.get(f"/api/v1/admin/users/{user.id}/activation-links")
    assert r.status_code == 200
    links = r.json()
    assert len(links) >= 1
    assert links[0]["status"] == "active"


# ── POST /admin/batch-activation-links ──


def test_batch_activation_links(db, admin_client):
    """Admin can batch-generate activation links."""
    event, _ = create_test_event(db, name="Batch Evt")
    create_test_user(
        db, username="batch1", event_id=event.id, is_activated=False,
    )
    create_test_user(
        db, username="batch2", event_id=event.id, is_activated=False,
    )

    r = admin_client.post("/api/v1/admin/batch-activation-links", json={
        "event_id": event.id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 2


def test_batch_activation_links_issuer_scoped(db):
    """Issuer batch-generates links for own event only."""
    event1, _ = create_test_event(db, name="Evt1")
    event2, _ = create_test_event(db, name="Evt2")
    create_test_user(
        db, username="batch_e1", event_id=event1.id, is_activated=False,
    )
    create_test_user(
        db, username="batch_e2", event_id=event2.id, is_activated=False,
    )

    issuer = create_test_user(
        db, username="iss_batch", is_issuer=True, event_id=event1.id,
    )
    client = _make_client(db, issuer)

    r = client.post("/api/v1/admin/batch-activation-links", json={
        "event_id": event2.id,  # tries other event
    })
    assert r.status_code == 200
    data = r.json()
    # Only event1 users should get links
    for link in data["links"]:
        assert link["username"] == "batch_e1"


# ── DELETE /admin/users/{id}/activation-links/{link_id} ──


def test_invalidate_activation_link(db, admin_client):
    """Admin can invalidate a specific activation link."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="inv_link", event_id=event.id, is_activated=False,
    )
    admin_client.post(f"/api/v1/admin/users/{user.id}/activation-link")

    # Get link ID
    links_r = admin_client.get(f"/api/v1/admin/users/{user.id}/activation-links")
    link_id = links_r.json()[0]["id"]

    r = admin_client.delete(
        f"/api/v1/admin/users/{user.id}/activation-links/{link_id}",
    )
    assert r.status_code == 200

    # Verify it's invalidated
    links_r2 = admin_client.get(f"/api/v1/admin/users/{user.id}/activation-links")
    assert links_r2.json()[0]["status"] == "invalidated"


# ── Activation flow: validate + complete ──


def test_activation_validate_token(db, admin_client):
    """Activation token can be validated via the activation endpoint."""
    event, _ = create_test_event(db, name="Evt")
    user = create_test_user(
        db, username="activate_me", event_id=event.id, is_activated=False,
    )
    r = admin_client.post(f"/api/v1/admin/users/{user.id}/activation-link")
    activation_url = r.json()["activation_url"]
    token = activation_url.split("token=")[1]

    # Validate
    r2 = admin_client.get(f"/api/v1/activation/validate?token={token}")
    # Should return user info (200) or the validation response
    assert r2.status_code == 200
