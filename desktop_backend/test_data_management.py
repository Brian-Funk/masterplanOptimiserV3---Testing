"""Tests for data management endpoints — export, import, copy-from-event."""
from datetime import date, datetime

from sqlalchemy import text

from app.models.event import Event
from app.models.location import Location
from app.models.person import Person
from app.models.privacy import PersonUnavailability
from app.models.task_instance import TaskInstance
from app.models.task_template import TaskTemplate

from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)


def valid_import_payload():
    """Return a compact valid project export for preview and import tests."""
    return {
        "version": 2,
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


def create_copy_event(db, name, start_date, end_date, *, overnight=False):
    """Create an event with an explicit date range for copy tests."""
    event = Event(
        name=name,
        start_date=start_date,
        end_date=end_date,
        meta_data={
            "schedule_day_range": {
                "startHour": 6,
                "endHour": 28 if overnight else 24,
            }
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_copy_template(db):
    """Create a task template with a concrete start/end time field."""
    template = TaskTemplate(
        machine_name="copy_test_task",
        name="Copy Test Task",
        fields=[
            {
                "id": "slot",
                "name": "Time",
                "type": "start_end_time",
                "category": "conditions",
            }
        ],
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


# ═══════════════════════════════════════════════════════════
# COPY FROM EVENT
# ═══════════════════════════════════════════════════════════


def test_copy_task_structure_maps_relative_and_overnight_dates(db, client):
    """Task structure is shifted to target working days, including overnight dates."""
    source = create_copy_event(
        db, "Source", date(2026, 8, 1), date(2026, 8, 3), overnight=True
    )
    target = create_copy_event(
        db, "Target", date(2026, 9, 10), date(2026, 9, 12), overnight=True
    )
    template = create_copy_template(db)
    db.add_all([
        TaskInstance(
            event_id=source.id,
            template_id=template.id,
            name="Day two task",
            date="2026-08-02",
            day_index=1,
            field_values={"slot": {"start": "10:00", "end": "11:00"}},
        ),
        TaskInstance(
            event_id=source.id,
            template_id=template.id,
            name="Final night task",
            date="2026-08-04",
            day_index=2,
            field_values={"slot": {"start": "02:00", "end": "03:00"}},
        ),
    ])
    db.commit()

    response = client.post(
        "/api/v1/data/copy-from-event",
        json={
            "source_event_id": source.id,
            "target_event_id": target.id,
            "include": ["task_structure"],
        },
    )

    assert response.status_code == 200
    copied = (
        db.query(TaskInstance)
        .filter(TaskInstance.event_id == target.id)
        .order_by(TaskInstance.id)
        .all()
    )
    assert [(item.date, item.day_index) for item in copied] == [
        ("2026-09-11", 1),
        ("2026-09-13", 2),
    ]
    assert all(item.optimised is None and item.final is None for item in copied)


def test_copy_task_structure_blocks_short_target_atomically(db, client):
    """An undersized target rejects the complete copy before any selected data is written."""
    source = create_copy_event(db, "Source", date(2026, 8, 1), date(2026, 8, 3))
    target = create_copy_event(db, "Target", date(2026, 9, 10), date(2026, 9, 10))
    template = create_copy_template(db)
    db.add(Location(event_id=source.id, name="Source hall"))
    db.add(TaskInstance(
        event_id=source.id,
        template_id=template.id,
        name="Third day task",
        date="2026-08-03",
        day_index=2,
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
    ))
    db.commit()

    response = client.post(
        "/api/v1/data/copy-from-event",
        json={
            "source_event_id": source.id,
            "target_event_id": target.id,
            "include": ["locations", "task_structure"],
        },
    )

    assert response.status_code == 400
    assert "target project has only 1 day" in response.json()["detail"]
    assert db.query(Location).filter(Location.event_id == target.id).count() == 0
    assert db.query(TaskInstance).filter(TaskInstance.event_id == target.id).count() == 0


def test_copy_persons_assigns_unavailability_to_target_event(db, client):
    """Copied availability intervals belong to both the copied person and target event."""
    source = create_copy_event(db, "Source", date(2026, 8, 1), date(2026, 8, 2))
    target = create_copy_event(db, "Target", date(2026, 9, 1), date(2026, 9, 2))
    person = create_test_person(db, source.id, "Copy", "Subject")
    db.add(PersonUnavailability(
        event_id=source.id,
        person_id=person.id,
        starts_at=datetime(2026, 8, 1, 9),
        ends_at=datetime(2026, 8, 1, 10),
    ))
    db.commit()

    response = client.post(
        "/api/v1/data/copy-from-event",
        json={
            "source_event_id": source.id,
            "target_event_id": target.id,
            "include": ["persons"],
        },
    )

    assert response.status_code == 200
    copied_person = db.query(Person).filter(Person.event_id == target.id).one()
    interval = db.query(PersonUnavailability).filter(
        PersonUnavailability.person_id == copied_person.id
    ).one()
    assert interval.event_id == target.id
    assert interval.starts_at == datetime(2026, 8, 1, 9)
    assert interval.ends_at == datetime(2026, 8, 1, 10)


def test_copied_task_date_repair_previews_and_applies_safe_skeletons(db, client):
    """Repair changes only selected unscheduled skeletons that still match the source."""
    source = create_copy_event(db, "Source", date(2026, 8, 1), date(2026, 8, 3))
    target = create_copy_event(db, "Target", date(2026, 9, 10), date(2026, 9, 12))
    template = create_copy_template(db)
    source_task = TaskInstance(
        event_id=source.id,
        template_id=template.id,
        name="Copied skeleton",
        date="2026-08-02",
        day_index=1,
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
    )
    stale_copy = TaskInstance(
        event_id=target.id,
        template_id=template.id,
        name="Copied skeleton",
        date="2026-08-02",
        day_index=1,
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
    )
    scheduled_copy = TaskInstance(
        event_id=target.id,
        template_id=template.id,
        name="Copied skeleton",
        date="2026-08-02",
        day_index=1,
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
        final={"start_time": 600, "end_time": 660},
    )
    db.add_all([source_task, stale_copy, scheduled_copy])
    db.commit()
    db.refresh(stale_copy)
    db.refresh(scheduled_copy)

    preview = client.post(
        "/api/v1/data/copy-from-event/repair-preview",
        json={"source_event_id": source.id, "target_event_id": target.id},
    )

    assert preview.status_code == 200
    assert preview.json()["repairable_count"] == 1
    assert preview.json()["candidates"] == [{
        "task_instance_id": stale_copy.id,
        "name": "Copied skeleton",
        "current_date": "2026-08-02",
        "proposed_date": "2026-09-11",
        "proposed_day_index": 1,
        "repairable": True,
        "reason": None,
    }]

    applied = client.post(
        "/api/v1/data/copy-from-event/repair",
        json={
            "source_event_id": source.id,
            "target_event_id": target.id,
            "task_instance_ids": [stale_copy.id],
        },
    )

    assert applied.status_code == 200
    db.refresh(stale_copy)
    db.refresh(scheduled_copy)
    assert (stale_copy.date, stale_copy.day_index) == ("2026-09-11", 1)
    assert scheduled_copy.date == "2026-08-02"


def test_copied_task_date_repair_rejects_stale_selection(db, client):
    """Repair refuses IDs that no longer belong to the current safe preview."""
    source = create_copy_event(db, "Source", date(2026, 8, 1), date(2026, 8, 2))
    target = create_copy_event(db, "Target", date(2026, 9, 10), date(2026, 9, 11))
    template = create_copy_template(db)
    source_task = TaskInstance(
        event_id=source.id,
        template_id=template.id,
        name="Copied skeleton",
        date="2026-08-01",
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
    )
    stale_copy = TaskInstance(
        event_id=target.id,
        template_id=template.id,
        name="Copied skeleton",
        date="2026-08-01",
        field_values={"slot": {"start": "10:00", "end": "11:00"}},
    )
    db.add_all([source_task, stale_copy])
    db.commit()
    db.refresh(stale_copy)

    stale_copy.name = "Changed after preview"
    db.commit()
    response = client.post(
        "/api/v1/data/copy-from-event/repair",
        json={
            "source_event_id": source.id,
            "target_event_id": target.id,
            "task_instance_ids": [stale_copy.id],
        },
    )

    assert response.status_code == 409
    assert "preview is stale" in response.json()["detail"]


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


def test_import_remaps_unavailability_to_imported_event(db, client):
    """Imported intervals use the new event and person identifiers."""
    create_test_event(db, name="Existing")
    payload = valid_import_payload()
    payload["global_data"] = {
        key: [] for key in payload["global_data"]
    }
    payload["events"][0]["tasks"] = []
    payload["events"][0]["assignments"] = []
    payload["events"][0]["optimization_jobs"] = []
    payload["events"][0]["person_unavailabilities"] = [{
        "id": 1,
        "event_id": 1,
        "person_id": 1,
        "starts_at": "2026-08-01T09:00:00",
        "ends_at": "2026-08-01T10:00:00",
    }]

    response = client.post("/api/v1/data/import", json={"data": payload})

    assert response.status_code == 200
    imported_event_id = response.json()["imported_event_ids"][0]
    imported_person = db.query(Person).filter(Person.event_id == imported_event_id).one()
    interval = db.query(PersonUnavailability).one()
    assert imported_event_id != 1
    assert interval.event_id == imported_event_id
    assert interval.person_id == imported_person.id


def test_import_rejects_existing_accountability_identities_before_mutation(db, client):
    """Restoring over the source project reports a conflict instead of a 500."""
    event = create_test_event(db, name="Existing")
    create_test_person(db, event.id, "Existing", "Subject")
    exported = client.post(
        "/api/v1/data/export",
        json={"scope": "event", "event_ids": [event.id]},
    ).json()

    response = client.post("/api/v1/data/import", json={"data": exported})

    assert response.status_code == 409
    assert response.json()["detail"]["event_identity_conflicts"] == 1
    assert response.json()["detail"]["person_identity_conflicts"] == 1
    assert db.query(Event).count() == 1
    assert db.query(Person).count() == 1


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


def test_event_delete_and_factory_reset_remove_unavailability(db, client):
    """Both destructive data-management paths erase typed availability rows."""
    event = create_test_event(db, name="Delete availability")
    person = create_test_person(db, event.id, "Delete", "Subject")
    db.add(PersonUnavailability(
        event_id=event.id,
        person_id=person.id,
        starts_at=datetime(2026, 8, 1, 9),
        ends_at=datetime(2026, 8, 1, 10),
    ))
    db.commit()

    deleted = client.delete(f"/api/v1/data/event/{event.id}")

    assert deleted.status_code == 200
    assert db.query(PersonUnavailability).count() == 0

    reset_event = create_test_event(db, name="Reset availability")
    reset_person = create_test_person(db, reset_event.id, "Reset", "Subject")
    db.add(PersonUnavailability(
        event_id=reset_event.id,
        person_id=reset_person.id,
        starts_at=datetime(2026, 8, 1, 11),
        ends_at=datetime(2026, 8, 1, 12),
    ))
    db.commit()

    reset = client.post("/api/v1/data/factory-reset", json={"confirmation": "RESET"})

    assert reset.status_code == 200
    assert db.query(PersonUnavailability).count() == 0
