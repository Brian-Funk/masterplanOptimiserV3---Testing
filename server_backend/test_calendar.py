"""Tests for calendar endpoints."""
import json
from datetime import datetime, timezone

from server_backend.conftest import (
    _make_client,
    _raw_client,
    create_test_event,
    create_test_user,
)
from app.models.published import (
    PublishedGeneralScheduleCategory,
    PublishedGeneralScheduleItem,
    PublishedTask,
    PublishedPerson,
    TaskEdit,
)


def _seed_published_data(db, event_id: int):
    """Insert published tasks and persons for testing."""
    person = PublishedPerson(
        event_id=event_id,
        external_person_id=1,
        first_name="Jane",
        last_name="Doe",
        email="jane@test.com",
    )
    db.add(person)

    task = PublishedTask(
        event_id=event_id,
        external_task_id=1,
        name="Workshop A",
        start_datetime=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        attendees_json='[{"name": "Jane Doe", "person_id": 1}]',
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task, person


def test_get_calendar(db):
    """Authenticated user can get calendar data for their event."""
    event, _ = create_test_event(db, name="Cal Evt")
    _seed_published_data(db, event.id)

    user = create_test_user(
        db, username="cal_user", event_id=event.id, can_edit=True,
    )
    client = _make_client(db, user)

    r = client.get(f"/api/v1/calendar/{event.id}")
    assert r.status_code == 200
    data = r.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["name"] == "Workshop A"


def test_get_calendar_persons(db):
    """Can get published persons for an event."""
    event, _ = create_test_event(db, name="Pers Evt")
    _seed_published_data(db, event.id)

    user = create_test_user(
        db, username="pers_user", event_id=event.id,
    )
    client = _make_client(db, user)

    r = client.get(f"/api/v1/calendar/{event.id}/persons")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["first_name"] == "Jane"


def test_get_calendar_returns_public_schedule_views(db):
    """Calendar payload includes published public schedule views."""
    event, _ = create_test_event(db, name="Schedule View Evt")
    db.add(
        PublishedGeneralScheduleCategory(
            event_id=event.id,
            external_category_id=10,
            name="Delegates",
            sort_order=0,
        )
    )
    db.add(
        PublishedGeneralScheduleItem(
            event_id=event.id,
            external_session_element_id=100,
            title="Opening Briefing",
            date="2026-08-01",
            start_time="09:00",
            end_time="10:00",
            category_id=10,
            category_name="Delegates",
        )
    )
    db.commit()
    user = create_test_user(db, username="schedule_user", event_id=event.id)
    client = _make_client(db, user)

    r = client.get(f"/api/v1/calendar/{event.id}")

    assert r.status_code == 200
    data = r.json()
    assert data["public_schedule_views"] == [
        {"id": 10, "name": "Delegates", "sort_order": 0.0},
    ]
    assert data["public_schedule_items"][0]["category_id"] == 10


def test_commit_preserves_structured_assignment_categories(db):
    """Web edits keep assignment fields separate instead of flattening them."""
    event, _ = create_test_event(db, name="Structured Assignments")
    task = PublishedTask(
        event_id=event.id,
        external_task_id=5,
        name="Meal Transfer",
        start_datetime=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        attendees_json=json.dumps([
            {"name": "Person A", "person_id": 1},
            {"name": "Person B", "person_id": 2},
        ]),
        field_assignments_json=json.dumps({
            "driver": [{"name": "Person A", "person_id": 1}],
            "cook": [{"name": "Person B", "person_id": 2}],
        }),
        field_definitions_json=json.dumps([
            {"id": "driver", "name": "Driver", "type": "persons_list"},
            {"id": "cook", "name": "Cook", "type": "persons_list"},
        ]),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    editor = create_test_user(
        db,
        username="structured.editor",
        event_id=event.id,
        can_edit=True,
    )
    client = _make_client(db, editor)

    added = client.post(
        f"/api/v1/calendar/{event.id}/tasks/commit",
        json={
            "edits": [
                {
                    "task_id": task.id,
                    "field_assignments": {
                        "driver": [{"name": "Person A", "person_id": 1}],
                        "cook": [
                            {"name": "Person B", "person_id": 2},
                            {"name": "Person C", "person_id": 3},
                        ],
                    },
                },
            ],
            "deletions": [],
            "creations": [],
        },
    )

    assert added.status_code == 200
    edit = db.query(TaskEdit).filter(TaskEdit.task_id == task.id).one()
    assert json.loads(edit.field_assignments_json) == {
        "driver": [{"name": "Person A", "person_id": 1}],
        "cook": [
            {"name": "Person B", "person_id": 2},
            {"name": "Person C", "person_id": 3},
        ],
    }
    assert json.loads(edit.attendees_json) == [
        {"name": "Person A", "person_id": 1},
        {"name": "Person B", "person_id": 2},
        {"name": "Person C", "person_id": 3},
    ]

    removed = client.post(
        f"/api/v1/calendar/{event.id}/tasks/commit",
        json={
            "edits": [
                {
                    "task_id": task.id,
                    "field_assignments": {
                        "driver": [{"name": "Person A", "person_id": 1}],
                        "cook": [{"name": "Person C", "person_id": 3}],
                    },
                },
            ],
            "deletions": [],
            "creations": [],
        },
    )

    assert removed.status_code == 200
    refreshed = client.get(f"/api/v1/calendar/{event.id}")
    assert refreshed.status_code == 200
    task_data = refreshed.json()["tasks"][0]
    assert task_data["field_assignments"] == {
        "driver": [{"name": "Person A", "person_id": 1}],
        "cook": [{"name": "Person C", "person_id": 3}],
    }
    assert task_data["attendees"] == [
        {"name": "Person A", "person_id": 1},
        {"name": "Person C", "person_id": 3},
    ]


def test_get_calendar_unauthenticated(db):
    """Calendar endpoint requires authentication."""
    event, _ = create_test_event(db, name="Unauth Evt")
    client = _raw_client()
    r = client.get(f"/api/v1/calendar/{event.id}")
    assert r.status_code == 401
