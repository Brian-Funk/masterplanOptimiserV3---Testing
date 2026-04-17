"""Tests for calendar endpoints."""
from server_backend.conftest import (
    create_test_event, create_test_user, _make_client,
)
from app.models.published import PublishedTask, PublishedPerson


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
        start_datetime="2026-08-01T09:00:00+00:00",
        end_datetime="2026-08-01T10:00:00+00:00",
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


def test_get_calendar_unauthenticated(db):
    """Calendar endpoint requires authentication."""
    from httpx import ASGITransport, Client
    from app.main import app

    event, _ = create_test_event(db, name="Unauth Evt")
    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
    )
    r = client.get(f"/api/v1/calendar/{event.id}")
    assert r.status_code == 401
