"""Tests for the optimization endpoint — job creation and status tracking."""
from desktop_backend.conftest import (
    create_test_event, create_test_location, create_test_person,
    create_test_task, create_test_task_type,
)
from app.models.optimization_job import OptimizationJob


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
    data = r.json()
    assert data["jobs"] == []
    assert data["running_job"] is None


def test_get_job_not_found(db, client):
    """Get non-existent job → 404."""
    event = create_test_event(db, name="No Matching Job")
    r = client.get(f"/api/v1/optimize/jobs/99999?event_id={event.id}")
    assert r.status_code == 404


def test_clear_stuck_jobs(db, client):
    """Clear stuck jobs endpoint runs without error."""
    event = create_test_event(db, name="Stuck Evt")
    r = client.post("/api/v1/optimize/clear-stuck-jobs", json={
        "event_id": event.id,
    })
    assert r.status_code == 200


def test_infeasible_solver_result_is_not_marked_completed(db, monkeypatch):
    """A proven conflict remains a diagnostic outcome, not a failed service."""
    from app.core import optimization_runner

    event = create_test_event(db, name="Unsatisfiable event")
    job = OptimizationJob(
        event_id=event.id,
        date="2026-08-01",
        status="pending",
        is_test_run=False,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    diagnostics = {
        "schema_version": 1,
        "status": "infeasible",
        "checked_scope": "full",
        "summary": "Task 'Briefing' cannot be fully staffed.",
        "issues": [
            {
                "code": "TASK_CANNOT_BE_COVERED",
                "category": "coverage",
                "severity": "error",
                "message": "Task 'Briefing' cannot be fully staffed.",
                "task_ids": [42],
                "person_ids": [],
                "transfer_ids": [],
                "location_ids": [],
                "capability_ids": [],
                "facts": [],
                "suggestions": ["Review overlapping staffing."],
            }
        ],
    }
    monkeypatch.setattr(optimization_runner, "SessionLocal", lambda: db)
    monkeypatch.setattr(optimization_runner.settings, "ENVIRONMENT", "desktop")
    monkeypatch.setattr(
        optimization_runner,
        "call_compute_service_sync",
        lambda _input, _request_id: {
            "status": "INFEASIBLE",
            "assignments": [],
            "progress_snapshots": [],
            "diagnostics": diagnostics,
        },
    )

    optimization_runner.run_optimization_background(job.id, {})

    saved = db.query(OptimizationJob).filter(OptimizationJob.id == job.id).one()
    assert saved.status == "infeasible"
    assert saved.error_message is None
    assert saved.result_data["diagnostics"] == diagnostics
    assert saved.progress_data["diagnostics"] == diagnostics
