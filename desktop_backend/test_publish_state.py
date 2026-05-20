"""Tests for persistent desktop publish-state metadata."""

from desktop_backend.conftest import create_test_event
from app.models.event_publish_state import EventPublishState


def test_publish_state_defaults_for_new_event(db, client):
    """A new event starts with empty, non-sensitive publish metadata."""
    event = create_test_event(db, name="Publish State Event")

    response = client.get(f"/api/v1/publish-state/{event.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event.id
    assert payload["published_schedule_fingerprint"] is None
    assert payload["published_schedule_scope"] == "none"
    assert payload["published_at"] is None
    assert payload["publish_failed_at"] is None
    assert payload["day_records"] == {}


def test_publish_state_saves_full_event_success(db, client):
    """Successful full-event publish metadata is saved and reloaded."""
    event = create_test_event(db, name="Publish State Event")

    response = client.put(
        f"/api/v1/publish-state/{event.id}",
        json={
            "published_schedule_fingerprint": "event-fingerprint",
            "published_schedule_scope": "all",
            "published_at": "2026-08-01T16:00:00Z",
            "publish_failed_at": None,
            "last_publish_target": "both",
            "last_publish_result_summary": "All 2 days published.",
            "day_records": {
                "2026-08-01": {
                    "fingerprint": "day-1",
                    "publishedAt": "2026-08-01T16:00:00Z",
                    "failedAt": None,
                    "failureMessage": None,
                },
                "2026-08-02": {
                    "fingerprint": "day-2",
                    "publishedAt": "2026-08-01T16:00:00Z",
                    "failedAt": None,
                    "failureMessage": None,
                },
            },
        },
    )

    assert response.status_code == 200

    reloaded = client.get(f"/api/v1/publish-state/{event.id}").json()
    assert reloaded["published_schedule_fingerprint"] == "event-fingerprint"
    assert reloaded["published_schedule_scope"] == "all"
    assert reloaded["published_at"] == "2026-08-01T16:00:00Z"
    assert reloaded["last_publish_target"] == "both"
    assert reloaded["day_records"]["2026-08-01"]["fingerprint"] == "day-1"


def test_publish_failure_updates_only_affected_days(db, client):
    """Failed publishing records failure state only for requested days."""
    event = create_test_event(db, name="Publish State Event")
    client.put(
        f"/api/v1/publish-state/{event.id}",
        json={
            "published_schedule_scope": "partial",
            "published_at": "2026-08-01T16:00:00Z",
            "day_records": {
                "2026-08-01": {
                    "fingerprint": "day-1",
                    "publishedAt": "2026-08-01T16:00:00Z",
                },
                "2026-08-02": {
                    "fingerprint": "day-2",
                    "publishedAt": "2026-08-01T16:00:00Z",
                },
            },
        },
    )

    response = client.post(
        f"/api/v1/publish-state/{event.id}/failure",
        json={
            "day_ids": ["2026-08-02"],
            "failed_at": "2026-08-01T16:20:00Z",
            "failure_message": "MP-Backend failed.",
            "last_publish_target": "mp-backend",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["publish_failed_at"] == "2026-08-01T16:20:00Z"
    assert payload["day_records"]["2026-08-01"].get("failedAt") is None
    assert payload["day_records"]["2026-08-02"]["failedAt"] == "2026-08-01T16:20:00Z"
    assert payload["day_records"]["2026-08-02"]["failureMessage"] == "MP-Backend failed."


def test_publish_state_clear_removes_event_metadata(db, client):
    """Clearing publish state returns the event to the default state."""
    event = create_test_event(db, name="Publish State Event")
    client.put(
        f"/api/v1/publish-state/{event.id}",
        json={
            "published_schedule_fingerprint": "event-fingerprint",
            "published_schedule_scope": "all",
            "published_at": "2026-08-01T16:00:00Z",
            "day_records": {},
        },
    )

    response = client.delete(f"/api/v1/publish-state/{event.id}")

    assert response.status_code == 200
    reloaded = client.get(f"/api/v1/publish-state/{event.id}").json()
    assert reloaded["published_schedule_fingerprint"] is None
    assert reloaded["published_schedule_scope"] == "none"
    assert reloaded["day_records"] == {}


def test_publish_state_is_removed_when_event_is_deleted(db, client):
    """Deleting an event also removes its persisted publish metadata."""
    event = create_test_event(db, name="Publish State Event")
    event_id = event.id
    client.put(
        f"/api/v1/publish-state/{event_id}",
        json={
            "published_schedule_fingerprint": "event-fingerprint",
            "published_schedule_scope": "all",
            "published_at": "2026-08-01T16:00:00Z",
            "day_records": {},
        },
    )

    response = client.delete(f"/api/v1/events/{event_id}")

    assert response.status_code == 200
    remaining = (
        db.query(EventPublishState)
        .filter(EventPublishState.event_id == event_id)
        .count()
    )
    assert remaining == 0


def test_publish_state_rejects_missing_event(client):
    """Publish metadata cannot be written for a missing event."""
    response = client.put(
        "/api/v1/publish-state/999999",
        json={"published_schedule_scope": "all", "day_records": {}},
    )

    assert response.status_code == 404
