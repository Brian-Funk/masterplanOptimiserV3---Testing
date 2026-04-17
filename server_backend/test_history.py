"""Tests for publish snapshot history endpoints."""
import json

from server_backend.conftest import (
    create_test_event, create_test_user, _make_client,
)
from app.models.published import PublishSnapshot


def _create_snapshot(db, event_id: int, version: int = 1, frozen: bool = False):
    """Helper to insert a snapshot directly."""
    snap = PublishSnapshot(
        event_id=event_id,
        version=version,
        snapshot_json=json.dumps({"tasks": [], "persons": []}),
        content_hash="abc123" + str(version),
        task_count=0,
        person_count=0,
        edits_count=0,
        source="test",
        frozen=frozen,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


# ── GET /admin/events/{event_id}/history ──


def test_list_snapshots(db, admin_client):
    """Admin can list snapshots for an event."""
    event, _ = create_test_event(db, name="Hist Evt")
    _create_snapshot(db, event.id, version=1)
    _create_snapshot(db, event.id, version=2)

    r = admin_client.get(f"/api/v1/admin/events/{event.id}/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["version"] == 2  # newest first


def test_list_snapshots_issuer(db):
    """Issuer can list snapshots for their own event."""
    event, _ = create_test_event(db, name="Iss Hist Evt")
    _create_snapshot(db, event.id, version=1)
    issuer = create_test_user(
        db, username="iss_hist", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.get(f"/api/v1/admin/events/{event.id}/history")
    assert r.status_code == 200


# ── GET /admin/events/{event_id}/history/{version} ──


def test_get_snapshot_detail(db, admin_client):
    """Admin can get full snapshot detail."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)

    r = admin_client.get(f"/api/v1/admin/events/{event.id}/history/1")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert "snapshot" in data


def test_get_snapshot_not_found(db, admin_client):
    """Getting non-existent snapshot version → 404."""
    event, _ = create_test_event(db, name="Evt")
    r = admin_client.get(f"/api/v1/admin/events/{event.id}/history/999")
    assert r.status_code == 404


# ── PATCH /admin/events/{event_id}/history/{version} ──


def test_patch_snapshot_label(db, admin_client):
    """Admin can set a label on a snapshot."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)

    r = admin_client.patch(
        f"/api/v1/admin/events/{event.id}/history/1",
        json={"label": "Release 1.0"},
    )
    assert r.status_code == 200
    assert r.json()["label"] == "Release 1.0"


def test_patch_snapshot_freeze(db, admin_client):
    """Admin can freeze a snapshot."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)

    r = admin_client.patch(
        f"/api/v1/admin/events/{event.id}/history/1",
        json={"frozen": True},
    )
    assert r.status_code == 200
    assert r.json()["frozen"] is True


def test_patch_snapshot_issuer_can_label(db):
    """Issuer can label snapshots in their own event."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)
    issuer = create_test_user(
        db, username="iss_label", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.patch(
        f"/api/v1/admin/events/{event.id}/history/1",
        json={"label": "Issuer Label"},
    )
    assert r.status_code == 200


# ── DELETE /admin/events/{event_id}/history/{version} ──


def test_delete_snapshot_admin_only(db, admin_client):
    """Admin can delete a snapshot."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)

    r = admin_client.delete(f"/api/v1/admin/events/{event.id}/history/1")
    assert r.status_code == 200


def test_delete_snapshot_frozen_blocked(db, admin_client):
    """Cannot delete a frozen snapshot."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1, frozen=True)

    r = admin_client.delete(f"/api/v1/admin/events/{event.id}/history/1")
    assert r.status_code == 409


def test_delete_snapshot_issuer_blocked(db):
    """Issuer cannot delete snapshots (require_admin, not require_admin_or_issuer)."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)
    issuer = create_test_user(
        db, username="iss_del", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.delete(f"/api/v1/admin/events/{event.id}/history/1")
    assert r.status_code == 403


# ── POST /admin/events/{event_id}/history/{version}/restore ──


def test_restore_snapshot_admin_only(db):
    """Admin can restore a snapshot."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)
    admin = create_test_user(
        db, username="restore_admin", is_admin=True, event_id=event.id,
    )
    client = _make_client(db, admin)

    r = client.post(f"/api/v1/admin/events/{event.id}/history/1/restore")
    assert r.status_code == 200
    assert r.json()["restored_version"] == 1


def test_restore_snapshot_issuer_blocked(db):
    """Issuer cannot restore snapshots."""
    event, _ = create_test_event(db, name="Evt")
    _create_snapshot(db, event.id, version=1)
    issuer = create_test_user(
        db, username="iss_restore", is_issuer=True, event_id=event.id,
    )
    client = _make_client(db, issuer)

    r = client.post(f"/api/v1/admin/events/{event.id}/history/1/restore")
    assert r.status_code == 403
