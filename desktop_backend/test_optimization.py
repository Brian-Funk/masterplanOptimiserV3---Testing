"""Tests for the optimization endpoint — job creation and status tracking."""
from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)


def test_optimize_no_tasks(db, client):
    """Optimising event with no tasks → meaningful response or error."""
    event = create_test_event(db, name="Empty Evt")
    event.status = "draft"
    db.commit()

    r = client.post("/api/v1/optimize/day", json={
        "event_id": event.id,
        "date": "2026-08-01",
        "day_index": 0,
        "tasks": [],
        "persons": [],
        "locations": [],
        "capabilities": [],
    })
    # Either 200 with a job_id, or 400 for no tasks — both valid
    assert r.status_code in (200, 400, 422)


def test_list_jobs_empty(db, client):
    """List optimisation jobs for event with no jobs → empty list."""
    event = create_test_event(db, name="No Jobs")

    r = client.get(f"/api/v1/optimize/jobs?event_id={event.id}")
    assert r.status_code == 200
    assert r.json() == []


def test_get_job_not_found(db, client):
    """Get non-existent job → 404."""
    r = client.get("/api/v1/optimize/jobs/99999")
    assert r.status_code == 404


def test_clear_stuck_jobs(db, client):
    """Clear stuck jobs endpoint runs without error."""
    event = create_test_event(db, name="Stuck Evt")
    r = client.post("/api/v1/optimize/clear-stuck-jobs", json={
        "event_id": event.id,
    })
    assert r.status_code == 200
