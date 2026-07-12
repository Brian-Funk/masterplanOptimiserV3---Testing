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
    db.add_all([
        PublishedPerson(
            event_id=event.id,
            external_person_id=person_id,
            first_name="Person",
            last_name=letter,
        )
        for person_id, letter in ((1, "A"), (2, "B"), (3, "C"))
    ])
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


def test_commit_preserves_legacy_assignment_fields(db):
    """Editing one legacy persons_list value preserves every other category."""
    event, _ = create_test_event(db, name="Legacy Structured Assignments")
    db.add_all([
        PublishedPerson(
            event_id=event.id,
            external_person_id=person_id,
            first_name="Person",
            last_name=letter,
        )
        for person_id, letter in [(1, "A"), (2, "B"), (3, "C")]
    ])
    task = PublishedTask(
        event_id=event.id,
        external_task_id=6,
        name="Legacy Meal Transfer",
        start_datetime=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        attendees_json=json.dumps([
            {"name": "Person A", "person_id": 1},
            {"name": "Person B", "person_id": 2},
        ]),
        field_values_json=json.dumps({
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
        username="legacy.structured.editor",
        event_id=event.id,
        can_edit=True,
    )
    client = _make_client(db, editor)

    response = client.post(
        f"/api/v1/calendar/{event.id}/tasks/commit",
        json={
            "edits": [{
                "task_id": task.id,
                "field_assignments": {
                    "cook": [
                        {"name": "Person B", "person_id": 2},
                        {"name": "Person C", "person_id": 3},
                    ],
                },
            }],
            "deletions": [],
            "creations": [],
        },
    )

    assert response.status_code == 200
    edit = db.query(TaskEdit).filter(TaskEdit.task_id == task.id).one()
    assert json.loads(edit.field_assignments_json) == {
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
    refreshed_task = client.get(f"/api/v1/calendar/{event.id}").json()["tasks"][0]
    assert refreshed_task["field_values"]["driver"] == [
        {"name": "Person A", "person_id": 1},
    ]
    assert refreshed_task["field_assignments"]["cook"] == [
        {"name": "Person B", "person_id": 2},
        {"name": "Person C", "person_id": 3},
    ]


def test_get_calendar_unauthenticated(db):
    """Calendar endpoint requires authentication."""
    event, _ = create_test_event(db, name="Unauth Evt")
    client = _raw_client()
    r = client.get(f"/api/v1/calendar/{event.id}")
    assert r.status_code == 401


def test_calendar_rejects_cross_event_read(db):
    """Changing the event id cannot expose another event's schedule."""
    own_event, _ = create_test_event(db, name="Own Event")
    other_event, _ = create_test_event(db, name="Other Event")
    _seed_published_data(db, other_event.id)
    user = create_test_user(db, username="event.viewer", event_id=own_event.id)

    response = _make_client(db, user).get(
        f"/api/v1/calendar/{other_event.id}",
    )

    assert response.status_code == 403


def test_calendar_commit_rejects_user_without_edit_permission(db):
    """A viewer cannot submit a crafted task edit request."""
    event, _ = create_test_event(db, name="Read Only")
    task, _ = _seed_published_data(db, event.id)
    viewer = create_test_user(db, username="read.only", event_id=event.id)

    response = _make_client(db, viewer).post(
        f"/api/v1/calendar/{event.id}/tasks/commit",
        json={
            "edits": [{"task_id": task.id, "name": "Changed"}],
            "deletions": [],
            "creations": [],
        },
    )

    assert response.status_code == 403


def test_revert_cannot_delete_edit_from_another_event(db):
    """A task id from another event cannot be used to remove its edit."""
    own_event, _ = create_test_event(db, name="Own Edit Event")
    other_event, _ = create_test_event(db, name="Other Edit Event")
    task, _ = _seed_published_data(db, other_event.id)
    edit = TaskEdit(task_id=task.id, name="Protected edit")
    db.add(edit)
    db.commit()
    editor = create_test_user(
        db,
        username="scoped.editor",
        event_id=own_event.id,
        can_edit=True,
    )

    response = _make_client(db, editor).delete(
        f"/api/v1/calendar/{own_event.id}/tasks/{task.id}/edits",
    )

    assert response.status_code == 404
    assert db.query(TaskEdit).filter(TaskEdit.task_id == task.id).count() == 1
