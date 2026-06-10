"""Tests for MP-Backend publish day scoping."""

import app.api.v1.mp_backend as mp_backend_module
from app.models.task import Task
from desktop_backend.conftest import create_test_event, create_test_task_type


class FakeMpBackendResponse:
    """Minimal HTTP response returned by the fake MP-Backend client."""

    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = ""

    def json(self):
        return {
            "tasks_created": len(self._payload["tasks"]),
            "persons_created": len(self._payload["persons"]),
            "edits_cleared": 0,
        }


class FakeAsyncClient:
    """Capture outbound publish payloads without calling an external server."""

    captured_payloads = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers, json):
        self.captured_payloads.append(json)
        return FakeMpBackendResponse(json)


def create_publish_task(db, event_id, task_type_id, title, day):
    """Insert a task with concrete publish data for one event day."""
    task = Task(
        event_id=event_id,
        task_type_id=task_type_id,
        title=title,
        constraints={},
        optimised={"start_time": 600, "end_time": 660, "location": None},
        final={"start_time": 600, "end_time": 660, "location": None},
        additional={"date": day},
        is_floating=False,
        is_transfer=False,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_mp_backend_publish_filters_tasks_to_requested_day(db, client, monkeypatch):
    """Publishing one day sends only that day's tasks to MP-Backend."""
    event = create_test_event(db, name="Publish Event")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    create_publish_task(db, event.id, task_type.id, "Session Task", "2026-08-02")
    db.commit()

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish/{event.id}",
        json={"dates": ["2026-08-01"]},
    )

    assert response.status_code == 200
    assert response.json()["tasks_created"] == 1
    payload = FakeAsyncClient.captured_payloads[0]
    assert [task["name"] for task in payload["tasks"]] == ["Arrival Task"]


def test_mp_backend_publish_without_dates_sends_all_tasks(db, client, monkeypatch):
    """Publishing without a day subset preserves the existing all-event behaviour."""
    event = create_test_event(db, name="Publish Event")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    create_publish_task(db, event.id, task_type.id, "Session Task", "2026-08-02")
    db.commit()

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 200
    assert response.json()["tasks_created"] == 2
    payload = FakeAsyncClient.captured_payloads[0]
    assert [task["name"] for task in payload["tasks"]] == [
        "Arrival Task",
        "Session Task",
    ]
    assert "theme" not in payload


def test_mp_backend_publish_rejects_invalid_date(client, db):
    """Invalid day ids are rejected before any external publish call is made."""
    event = create_test_event(db, name="Publish Event")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    db.commit()

    response = client.post(
        f"/api/v1/mp-backend/publish/{event.id}",
        json={"dates": ["01.08.2026"]},
    )

    assert response.status_code == 400
    assert "Invalid publish date" in response.json()["detail"]
