"""Tests for MP-Backend publish day scoping."""

import app.api.v1.mp_backend as mp_backend_module
from app.models.task import Task
from app.models.general_schedule import (
    GeneralSchedulePublishState,
    ScheduleView,
    SessionElement,
)
from desktop_backend.conftest import create_test_event, create_test_task_type


class FakeMpBackendResponse:
    """Minimal HTTP response returned by the fake MP-Backend client."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        if "tasks" not in self._payload:
            return self._payload
        return {
            "tasks_created": len(self._payload["tasks"]),
            "persons_created": len(self._payload["persons"]),
            "edits_cleared": 0,
        }


class FakeAsyncClient:
    """Capture outbound publish payloads without calling an external server."""

    captured_payloads = []
    supports_scoped_publish = True

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers):
        return FakeMpBackendResponse({
            "status": "ok",
            "event_name": "Publish Event",
            "event_id": 1,
            "supports_scoped_publish": self.supports_scoped_publish,
        })

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
    FakeAsyncClient.supports_scoped_publish = True
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish/{event.id}",
        json={"dates": ["2026-08-01"]},
    )

    assert response.status_code == 200
    assert response.json()["tasks_created"] == 1
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["publish_scope"] == "dates"
    assert payload["dates"] == ["2026-08-01"]
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
    FakeAsyncClient.supports_scoped_publish = True
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 200
    assert response.json()["tasks_created"] == 2
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["publish_scope"] == "full"
    assert "dates" not in payload
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


def test_mp_backend_publish_refuses_selected_day_on_server_without_scoped_support(
    db,
    client,
    monkeypatch,
):
    """Older servers must not receive a one-day payload they would full-replace."""
    event = create_test_event(db, name="Publish Event")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    db.commit()

    FakeAsyncClient.captured_payloads = []
    FakeAsyncClient.supports_scoped_publish = False
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish/{event.id}",
        json={"dates": ["2026-08-01"]},
    )

    assert response.status_code == 409
    assert "does not support selected-day publishing" in response.json()["detail"]
    assert FakeAsyncClient.captured_payloads == []


def test_public_schedule_selected_day_publish_filters_items_and_clears_failure(
    db,
    client,
    monkeypatch,
):
    """A successful selected-day retry clears only that day's stale failure."""
    event = create_test_event(db, name="Public Programme")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    view = ScheduleView(event_id=event.id, name="Public", sort_order=0)
    db.add(view)
    db.flush()
    db.add_all(
        [
            SessionElement(
                event_id=event.id,
                title="Day One",
                date="2026-08-01",
                start_time="09:00",
                end_time="10:00",
                schedule_view_ids=[view.id],
                visibility="public",
            ),
            SessionElement(
                event_id=event.id,
                title="Day Two",
                date="2026-08-02",
                start_time="09:00",
                end_time="10:00",
                schedule_view_ids=[view.id],
                visibility="public",
            ),
        ]
    )
    state = GeneralSchedulePublishState(
        event_id=event.id,
        publish_failed_at="2026-07-12T12:56:26Z",
        last_error="MP-Backend server is not configured.",
        day_records={
            "2026-08-01": {
                "fingerprint": None,
                "published_at": None,
                "publish_failed_at": "2026-07-12T12:56:26Z",
                "failure_message": "MP-Backend server is not configured.",
                "item_count": 0,
            },
            "2026-08-02": {
                "fingerprint": None,
                "published_at": None,
                "publish_failed_at": "2026-07-12T13:00:00Z",
                "failure_message": "Another failure.",
                "item_count": 0,
            },
        },
    )
    db.add(state)
    db.commit()

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish-general-schedule/{event.id}",
        json={"dates": ["2026-08-01"]},
    )

    assert response.status_code == 200
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["publish_scope"] == "dates"
    assert payload["dates"] == ["2026-08-01"]
    assert [item["title"] for item in payload["items"]] == ["Day One"]
    db.refresh(state)
    assert state.day_records["2026-08-01"]["publish_failed_at"] is None
    assert state.day_records["2026-08-01"]["failure_message"] is None
    assert state.day_records["2026-08-02"]["failure_message"] == "Another failure."
    assert state.publish_failed_at == "2026-07-12T13:00:00Z"


def test_public_schedule_all_days_publish_sends_full_programme(
    db,
    client,
    monkeypatch,
):
    """Publishing all days sends one full replacement payload."""
    event = create_test_event(db, name="Public Programme")
    event.mp_backend_url = "https://mp.example.test"
    event.mp_backend_secret = "secret"
    view = ScheduleView(event_id=event.id, name="Public", sort_order=0)
    db.add(view)
    db.flush()
    db.add_all(
        [
            SessionElement(
                event_id=event.id,
                title=title,
                date=day,
                start_time="09:00",
                end_time="10:00",
                schedule_view_ids=[view.id],
                visibility="public",
            )
            for title, day in (
                ("Day One", "2026-08-01"),
                ("Day Two", "2026-08-02"),
            )
        ]
    )
    state = GeneralSchedulePublishState(
        event_id=event.id,
        publish_failed_at="2026-07-12T12:56:26Z",
        last_error="Previous failure.",
        day_records={
            "2026-08-01": {
                "fingerprint": None,
                "published_at": None,
                "publish_failed_at": "2026-07-12T12:56:26Z",
                "failure_message": "Previous failure.",
                "item_count": 0,
            }
        },
    )
    db.add(state)
    db.commit()

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish-general-schedule/{event.id}",
        json={},
    )

    assert response.status_code == 200
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["publish_scope"] == "full"
    assert payload["dates"] is None
    assert [item["title"] for item in payload["items"]] == ["Day One", "Day Two"]
    db.refresh(state)
    assert state.publish_failed_at is None
    assert state.last_error is None
    assert all(
        record["publish_failed_at"] is None
        and record["failure_message"] is None
        for record in state.day_records.values()
    )
