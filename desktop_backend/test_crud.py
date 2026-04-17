"""Tests for desktop CRUD endpoints — events, persons, tasks, locations."""
from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)


# ═══════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════


def test_auth_required(db, unauth_client):
    """Request without desktop token → 403."""
    r = unauth_client.get("/api/v1/events/")
    assert r.status_code == 403


def test_auth_exempt_health(db, unauth_client):
    """Health endpoint is exempt from desktop token."""
    r = unauth_client.get("/health")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════


def test_create_event(db, client):
    """POST /api/v1/events/ creates an event."""
    r = client.post("/api/v1/events/", json={
        "name": "Summer Camp",
        "location": "Zurich",
        "start_date": "2026-08-01",
        "end_date": "2026-08-10",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Summer Camp"
    assert data["status"] == "draft"


def test_list_events(db, client):
    """GET /api/v1/events/ returns all events."""
    create_test_event(db, name="Evt A")
    create_test_event(db, name="Evt B")

    r = client.get("/api/v1/events/")
    assert r.status_code == 200
    names = [e["name"] for e in r.json()]
    assert "Evt A" in names
    assert "Evt B" in names


def test_get_event(db, client):
    """GET /api/v1/events/{id} returns a single event."""
    event = create_test_event(db, name="My Event")
    r = client.get(f"/api/v1/events/{event.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "My Event"


def test_get_event_not_found(db, client):
    """GET /api/v1/events/999 → 404."""
    r = client.get("/api/v1/events/999")
    assert r.status_code == 404


def test_update_event(db, client):
    """PUT /api/v1/events/{id} updates event fields."""
    event = create_test_event(db, name="Old Name")
    r = client.put(f"/api/v1/events/{event.id}", json={
        "name": "New Name",
        "location": "Geneva",
        "start_date": "2026-09-01",
        "end_date": "2026-09-10",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_delete_event(db, client):
    """DELETE /api/v1/events/{id} removes the event."""
    event = create_test_event(db, name="To Delete")
    r = client.delete(f"/api/v1/events/{event.id}")
    assert r.status_code == 200

    r2 = client.get(f"/api/v1/events/{event.id}")
    assert r2.status_code == 404


def test_update_event_status(db, client):
    """PUT /api/v1/events/{id}/status updates event status."""
    event = create_test_event(db, name="Status Evt")
    r = client.put(f"/api/v1/events/{event.id}/status", json={
        "status": "optimised",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "optimised"


def test_update_event_status_invalid(db, client):
    """Invalid status value → 400."""
    event = create_test_event(db, name="Evt")
    r = client.put(f"/api/v1/events/{event.id}/status", json={
        "status": "invalid",
    })
    assert r.status_code == 400


# ═══════════════════════════════════════════════════════════
# LOCATIONS
# ═══════════════════════════════════════════════════════════


def test_create_location(db, client):
    """POST /api/v1/locations/ creates a location."""
    event = create_test_event(db)
    r = client.post(f"/api/v1/locations/?event_id={event.id}", json={
        "name": "Room A",
    })
    assert r.status_code in (200, 201)
    assert r.json()["name"] == "Room A"


def test_list_locations(db, client):
    """GET /api/v1/locations/ returns locations for an event."""
    event = create_test_event(db)
    create_test_location(db, event.id, name="Room X")
    create_test_location(db, event.id, name="Room Y")

    r = client.get(f"/api/v1/locations/?event_id={event.id}")
    assert r.status_code == 200
    names = [l["name"] for l in r.json()]
    assert "Room X" in names
    assert "Room Y" in names


# ═══════════════════════════════════════════════════════════
# PERSONS
# ═══════════════════════════════════════════════════════════


def test_create_person(db, client):
    """POST /api/v1/persons/ creates a person."""
    event = create_test_event(db)
    loc = create_test_location(db, event.id)
    r = client.post(f"/api/v1/persons/?event_id={event.id}", json={
        "first_name": "John",
        "last_name": "Smith",
        "home_location_id": loc.id,
    })
    assert r.status_code == 201
    assert r.json()["first_name"] == "John"


def test_list_persons(db, client):
    """GET /api/v1/persons/ returns persons for an event."""
    event = create_test_event(db)
    loc = create_test_location(db, event.id)
    create_test_person(db, event.id, "Alice", "A", loc.id)
    create_test_person(db, event.id, "Bob", "B", loc.id)

    r = client.get(f"/api/v1/persons/?event_id={event.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_person(db, client):
    """GET /api/v1/persons/{id} returns a single person."""
    event = create_test_event(db)
    loc = create_test_location(db, event.id)
    person = create_test_person(db, event.id, "Zara", "Z", loc.id)

    r = client.get(f"/api/v1/persons/{person.id}?event_id={event.id}")
    assert r.status_code == 200
    assert r.json()["first_name"] == "Zara"


def test_get_person_wrong_event(db, client):
    """Person from another event → 404."""
    event1 = create_test_event(db, name="Evt 1")
    event2 = create_test_event(db, name="Evt 2")
    loc = create_test_location(db, event1.id)
    person = create_test_person(db, event1.id, "Cross", "Evt", loc.id)

    r = client.get(f"/api/v1/persons/{person.id}?event_id={event2.id}")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════


def test_list_tasks(db, client):
    """GET /api/v1/tasks/ returns tasks for an event."""
    event = create_test_event(db)
    tt = create_test_task_type(db)
    create_test_task(db, event.id, tt.id, title="Task A")
    create_test_task(db, event.id, tt.id, title="Task B")

    r = client.get(f"/api/v1/tasks/?event_id={event.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_task(db, client):
    """GET /api/v1/tasks/{id} returns a single task."""
    event = create_test_event(db)
    tt = create_test_task_type(db)
    task = create_test_task(db, event.id, tt.id, title="My Task")

    r = client.get(f"/api/v1/tasks/{task.id}?event_id={event.id}")
    assert r.status_code == 200
    assert r.json()["title"] == "My Task"


def test_update_task(db, client):
    """PUT /api/v1/tasks/{id} updates task fields."""
    event = create_test_event(db)
    tt = create_test_task_type(db)
    task = create_test_task(db, event.id, tt.id, title="Old Title")

    r = client.put(f"/api/v1/tasks/{task.id}?event_id={event.id}", json={
        "title": "New Title",
        "additional": {"notes": "updated"},
    })
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"


def test_get_task_not_found(db, client):
    """GET /api/v1/tasks/999 → 404."""
    event = create_test_event(db)
    r = client.get(f"/api/v1/tasks/999?event_id={event.id}")
    assert r.status_code == 404


def test_delete_event_cascades(db, client):
    """Deleting an event also deletes its tasks and persons."""
    event = create_test_event(db)
    loc = create_test_location(db, event.id)
    tt = create_test_task_type(db)
    create_test_person(db, event.id, "Jane", "Doe", loc.id)
    create_test_task(db, event.id, tt.id, title="Task")

    client.delete(f"/api/v1/events/{event.id}")

    r_tasks = client.get(f"/api/v1/tasks/?event_id={event.id}")
    assert r_tasks.status_code == 200
    assert len(r_tasks.json()) == 0

    r_persons = client.get(f"/api/v1/persons/?event_id={event.id}")
    assert r_persons.status_code == 200
    assert len(r_persons.json()) == 0
