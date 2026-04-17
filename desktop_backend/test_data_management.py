"""Tests for data management endpoints — export, import, copy-from-event."""
from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)


# ═══════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════


def test_export_full(db, client):
    """Full export includes global data and all events."""
    event = create_test_event(db, name="Export Evt")
    loc = create_test_location(db, event.id)
    tt = create_test_task_type(db)
    create_test_person(db, event.id, "A", "B", loc.id)
    create_test_task(db, event.id, tt.id, title="T")

    r = client.post("/api/v1/data/export", json={"scope": "full"})
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "full_backup"
    assert "global_data" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["event"]["name"] == "Export Evt"


def test_export_global_only(db, client):
    """Global-only export has no events."""
    create_test_task_type(db, name="W")
    r = client.post("/api/v1/data/export", json={"scope": "global"})
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "app_settings"
    assert "events" not in data


def test_export_single_event(db, client):
    """Event-scoped export includes only the requested event."""
    evt1 = create_test_event(db, name="E1")
    evt2 = create_test_event(db, name="E2")

    r = client.post("/api/v1/data/export", json={
        "scope": "event",
        "event_ids": [evt1.id],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "project"
    assert len(data["events"]) == 1
    assert data["events"][0]["event"]["name"] == "E1"


def test_export_event_missing_ids(db, client):
    """Event export without event_ids → 400."""
    r = client.post("/api/v1/data/export", json={"scope": "event"})
    assert r.status_code == 400


# ═══════════════════════════════════════════════════════════
# IMPORT (round-trip)
# ═══════════════════════════════════════════════════════════


def test_import_roundtrip(db, client):
    """Export → import into clean DB recreates the data."""
    # Setup data
    tt = create_test_task_type(db, name="Workshop")
    event = create_test_event(db, name="Original")
    loc = create_test_location(db, event.id, name="Hall A")
    create_test_person(db, event.id, "Alice", "W", loc.id)
    create_test_task(db, event.id, tt.id, title="Opening")

    # Export
    r_export = client.post("/api/v1/data/export", json={"scope": "full"})
    assert r_export.status_code == 200
    exported = r_export.json()

    # Delete the event
    client.delete(f"/api/v1/events/{event.id}")
    r_check = client.get(f"/api/v1/events/{event.id}")
    assert r_check.status_code == 404

    # Import
    r_import = client.post("/api/v1/data/import", json={"data": exported})
    assert r_import.status_code == 200

    # Verify event was recreated
    r_events = client.get("/api/v1/events/")
    assert r_events.status_code == 200
    names = [e["name"] for e in r_events.json()]
    assert "Original" in names
