"""Tests for data management endpoints — export, import, copy-from-event."""
from sqlalchemy import text

from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)


def valid_import_payload():
    """Return a compact valid project export for preview and import tests."""
    return {
        "version": 1,
        "type": "project",
        "exported_at": "2026-05-20T10:00:00",
        "global_data": {
            "task_types": [{"id": 1, "machine_name": "session", "name": "Session"}],
            "task_templates": [
                {"id": 10, "machine_name": "workshop", "display_name": "Workshop"}
            ],
            "capabilities": [],
            "capability_types": [],
            "group_types": [],
            "leadership_levels": [],
            "group_roles": [],
            "assignment_sources": [],
            "calendar_export_formats": [],
        },
        "events": [
            {
                "event": {
                    "id": 1,
                    "name": "Import Event",
                    "location": "Zurich",
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-03",
                },
                "locations": [{"id": 1, "name": "Main Hall"}],
                "persons": [
                    {
                        "id": 1,
                        "first_name": "Ana",
                        "last_name": "Coric",
                        "email": "ana@example.test",
                        "home_location_id": 1,
                    }
                ],
                "tasks": [
                    {
                        "id": 1,
                        "title": "Opening Workshop",
                        "task_template_id": 10,
                        "task_type_id": 1,
                        "location_id": 1,
                        "optimised": {"start_time": "2026-08-01T10:00:00"},
                        "final": {"start_time": "2026-08-01T10:00:00"},
                    }
                ],
                "assignments": [
                    {"id": 1, "event_id": 1, "task_id": 1, "person_id": 1}
                ],
                "groups": [],
                "group_memberships": [],
                "person_capabilities": [],
                "task_capability_requirements": [],
                "task_instances": [],
                "masterplan_layouts": [],
                "optimization_jobs": [
                    {"id": 1, "event_id": 1, "status": "completed"}
                ],
            }
        ],
    }


def issue_titles(payload):
    """Collect all validation issue titles from a preview response."""
    return {
        issue["title"]
        for key in ("errors", "warnings", "info")
        for issue in payload.get(key, [])
    }


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
    event_id = event.id
    loc = create_test_location(db, event.id, name="Hall A")
    create_test_person(db, event.id, "Alice", "W", loc.id)
    create_test_task(db, event.id, tt.id, title="Opening")

    # Export
    r_export = client.post("/api/v1/data/export", json={"scope": "full"})
    assert r_export.status_code == 200
    exported = r_export.json()

    # Delete the event
    client.delete(f"/api/v1/events/{event_id}")
    r_check = client.get(f"/api/v1/events/{event_id}")
    assert r_check.status_code == 404

    # Import
    r_import = client.post("/api/v1/data/import", json={"data": exported})
    assert r_import.status_code == 200

    # Verify event was recreated
    r_events = client.get("/api/v1/events/")
    assert r_events.status_code == 200
    names = [e["name"] for e in r_events.json()]
    assert "Original" in names


def test_import_preview_summarises_valid_project_payload(client):
    """Preview returns counts and metadata without applying the import."""
    r = client.post(
        "/api/v1/data/import/preview",
        json={"data": valid_import_payload()},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is True
    assert data["errors"] == []
    assert data["summary"]["projectName"] == "Import Event"
    assert data["summary"]["dateRange"] == "01.08.2026 - 03.08.2026"
    assert data["summary"]["peopleCount"] == 1
    assert data["summary"]["locationCount"] == 1
    assert data["summary"]["taskCount"] == 1
    assert data["summary"]["templateCount"] == 1
    assert data["summary"]["assignmentCount"] == 1
    assert data["summary"]["hasOptimisedSchedule"] is True
    assert data["summary"]["hasFinalSchedule"] is True
    assert "File version" in issue_titles(data)


def test_import_preview_reports_missing_required_top_level_data(client):
    """Preview blocks payloads without required application settings."""
    r = client.post(
        "/api/v1/data/import/preview",
        json={"data": {"version": 1, "type": "project", "events": []}},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is False
    assert "Missing application settings" in issue_titles(data)


def test_import_preview_rejects_future_schema_version(client):
    """Preview blocks files exported by a newer unsupported schema."""
    payload = valid_import_payload()
    payload["version"] = 999

    r = client.post("/api/v1/data/import/preview", json={"data": payload})

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is False
    assert "File version too new" in issue_titles(data)


def test_import_preview_rejects_invalid_project_dates(client):
    """Preview catches invalid dates before import mutation."""
    payload = valid_import_payload()
    payload["events"][0]["event"]["start_date"] = "08/01/2026"
    payload["events"][0]["event"]["end_date"] = "2026-07-31"

    r = client.post("/api/v1/data/import/preview", json={"data": payload})

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is False
    assert "Invalid project date" in issue_titles(data)


def test_import_preview_rejects_missing_references(client):
    """Preview blocks imported rows that reference missing project data."""
    payload = valid_import_payload()
    payload["events"][0]["assignments"][0]["person_id"] = 999
    payload["events"][0]["tasks"][0]["task_template_id"] = 999

    r = client.post("/api/v1/data/import/preview", json={"data": payload})

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is False
    assert "Assignment references missing person" in issue_titles(data)
    assert "Task references missing template" in issue_titles(data)


def test_import_preview_warns_for_sparse_but_usable_payload(client):
    """Preview warns, but does not block, sparse project imports."""
    payload = valid_import_payload()
    payload["events"][0]["persons"] = []
    payload["events"][0]["tasks"] = []
    payload["events"][0]["assignments"] = []

    r = client.post("/api/v1/data/import/preview", json={"data": payload})

    assert r.status_code == 200
    data = r.json()
    assert data["isValid"] is True
    assert "No people included" in issue_titles(data)
    assert "No tasks included" in issue_titles(data)


def test_import_preview_warns_about_publish_metadata(client):
    """Preview notes that publish credentials are not imported from JSON."""
    payload = valid_import_payload()
    payload["events"][0]["event"]["mp_backend_url"] = "https://example.test"
    payload["events"][0]["event"]["mp_backend_secret"] = "not-imported"

    r = client.post("/api/v1/data/import/preview", json={"data": payload})

    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["hasPublishMetadata"] is True
    assert "Reconnect integrations after import" in issue_titles(data)


def test_import_rejects_invalid_payload_before_mutation(db, client):
    """Invalid imports fail before creating, deleting, or changing projects."""
    create_test_event(db, name="Existing")

    r = client.post(
        "/api/v1/data/import",
        json={"data": {"version": 999, "global_data": {}}},
    )

    assert r.status_code == 400
    assert r.json()["detail"]["message"] == "Import validation failed"
    events = client.get("/api/v1/events/").json()
    assert [event["name"] for event in events] == ["Existing"]


def test_data_management_delete_skips_absent_optional_tables(db, client):
    """Data-management delete works when optional legacy tables are absent."""
    event = create_test_event(db, name="Delete Me")
    event_id = event.id
    db.execute(text("DROP TABLE IF EXISTS attachments"))
    db.execute(text("DROP TABLE IF EXISTS task_descriptions"))
    db.commit()

    r = client.delete(f"/api/v1/data/event/{event_id}")

    assert r.status_code == 200
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404
