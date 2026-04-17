"""Tests for the desktop-to-server publish endpoint."""
from server_backend.conftest import create_test_event, create_test_user

from httpx import ASGITransport, Client


def _publish_client(bearer_token: str) -> Client:
    """Create a client with Bearer token auth (no session cookies)."""
    from app.main import app
    return Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        },
    )


_MINIMAL_PAYLOAD = {
    "tasks": [
        {
            "id": 1,
            "name": "Opening Ceremony",
            "start": "2026-08-01T09:00:00+00:00",
            "end": "2026-08-01T10:00:00+00:00",
            "attendees": [{"name": "John Doe", "person_id": 1}],
        },
    ],
    "persons": [
        {"id": 1, "first_name": "John", "last_name": "Doe"},
    ],
}


def test_publish_valid_token(db):
    """Publish with valid Bearer token → 200."""
    event, secret = create_test_event(db, name="Pub Evt")
    client = _publish_client(secret)

    r = client.post("/api/v1/publish/publish", json=_MINIMAL_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["tasks_created"] == 1
    assert data["persons_created"] == 1


def test_publish_invalid_token(db):
    """Publish with invalid Bearer token → 401."""
    create_test_event(db, name="Pub Evt")
    client = _publish_client("invalid-secret-token")

    r = client.post("/api/v1/publish/publish", json=_MINIMAL_PAYLOAD)
    assert r.status_code == 401


def test_publish_no_token(db):
    """Publish without Bearer token → 401."""
    from app.main import app
    client = Client(
        transport=ASGITransport(app=app),
        base_url="https://localhost",
        headers={"Content-Type": "application/json"},
    )
    r = client.post("/api/v1/publish/publish", json=_MINIMAL_PAYLOAD)
    assert r.status_code == 401


def test_publish_creates_data(db):
    """Published data is stored and retrievable."""
    event, secret = create_test_event(db, name="Data Evt")
    client = _publish_client(secret)
    client.post("/api/v1/publish/publish", json=_MINIMAL_PAYLOAD)

    from app.models.published import PublishedTask, PublishedPerson
    tasks = db.query(PublishedTask).filter(
        PublishedTask.event_id == event.id,
    ).all()
    persons = db.query(PublishedPerson).filter(
        PublishedPerson.event_id == event.id,
    ).all()
    assert len(tasks) == 1
    assert tasks[0].name == "Opening Ceremony"
    assert len(persons) == 1
    assert persons[0].first_name == "John"


def test_publish_replaces_existing(db):
    """Re-publish wipes old data and inserts new."""
    event, secret = create_test_event(db, name="Replace Evt")
    client = _publish_client(secret)

    # First publish
    client.post("/api/v1/publish/publish", json=_MINIMAL_PAYLOAD)

    # Second publish with different data
    new_payload = {
        "tasks": [
            {
                "id": 2,
                "name": "Closing Ceremony",
                "start": "2026-08-10T18:00:00+00:00",
                "end": "2026-08-10T19:00:00+00:00",
                "attendees": [],
            },
        ],
        "persons": [],
    }
    r = client.post("/api/v1/publish/publish", json=new_payload)
    assert r.status_code == 200
    assert r.json()["tasks_created"] == 1

    from app.models.published import PublishedTask
    tasks = db.query(PublishedTask).filter(
        PublishedTask.event_id == event.id,
    ).all()
    assert len(tasks) == 1
    assert tasks[0].name == "Closing Ceremony"


def test_publish_updates_event_metadata(db):
    """Publish can update event name and dates."""
    event, secret = create_test_event(db, name="Old Name")
    client = _publish_client(secret)

    payload = {
        "event": {
            "name": "New Name",
            "start_date": "2026-08-01",
            "end_date": "2026-08-10",
        },
        "tasks": [],
        "persons": [],
    }
    r = client.post("/api/v1/publish/publish", json=payload)
    assert r.status_code == 200

    db.refresh(event)
    assert event.name == "New Name"
    assert event.status == "published"
