"""Tests for MP-Backend publish day scoping."""

import hashlib
import json
from datetime import datetime

import app.api.v1.mp_backend as mp_backend_module
from app.core.secure_credentials import mp_backend_secret_key
from app.models.location import Location
from app.models.assignment import Assignment
from app.models.group import Group
from app.models.person import Person
from app.models.privacy import PersonUnavailability
from app.models.task import Task
from app.models.task_template import TaskTemplate
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

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    """Capture outbound publish payloads without calling an external server."""

    captured_payloads = []
    supports_scoped_publish = True
    policy_version = 7
    policy_sha256 = "a" * 64

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        if url.endswith("/api/v1/governance/public"):
            return FakeMpBackendResponse({
                "configured": True,
                "version": self.policy_version,
                "content_sha256": self.policy_sha256,
                "permitted_data": {
                    "purpose": "Operational event scheduling",
                    "allowed": ["names", "event roles"],
                    "unsupported": ["health", "unrelated private information"],
                },
            })
        return FakeMpBackendResponse({
            "status": "ok",
            "event_name": "Publish Event",
            "event_id": 1,
            "supports_scoped_publish": self.supports_scoped_publish,
        })

    async def post(self, url, headers, json):
        self.captured_payloads.append(json)
        return FakeMpBackendResponse(json)


def acknowledge_current_policy(db, event_id):
    """Seed the exact pseudonymous Desktop acknowledgement required to publish."""
    mp_backend_module._set_setting(
        db,
        mp_backend_module._policy_ack_key(event_id),
        json.dumps({
            "policy_version": 7,
            "policy_sha256": "a" * 64,
            "operator_subject": "b" * 64,
            "acknowledged_at": "2026-07-30T12:00:00+00:00",
        }),
    )
    db.commit()


def configure_mp_backend(event, secure_credential_store):
    """Configure the URL and secure publish secret through the Phase 1 boundary."""
    event.mp_backend_url = "https://mp.example.test"
    secure_credential_store.values[mp_backend_secret_key(event.id)] = "secret"


def test_public_schedule_fingerprint_matches_browser_number_serialisation():
    """Whole-number database floats hash exactly like browser JSON numbers."""
    items = [
        {
            "id": 2,
            "title": "Second",
            "date": "2026-08-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "location_name": "Hall A",
            "location_address": "1 Main Street",
            "schedule_view_ids": [20],
            "schedule_view_names": ["Board"],
            "schedule_view_sort_orders": {"20": 2.0},
            "responsible": " ",
            "description": "",
            "colour": "#7dd3fc",
            "copy_template_html": "",
            "sort_order": 10.0,
        },
        {
            "id": 1,
            "title": "First",
            "date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "location_name": None,
            "location_address": None,
            "schedule_view_ids": [20],
            "schedule_view_names": ["Board"],
            "schedule_view_sort_orders": {"20": 2.0},
            "colour": "#7dd3fc",
            "sort_order": 5.0,
        },
    ]
    browser_payload = [
        {
            "id": item["id"],
            "title": item["title"],
            "type_id": None,
            "date": item["date"],
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "location_name": item["location_name"],
            "location_address": item["location_address"],
            "audience_teams": [],
            "schedule_views": [{"id": 20, "name": "Board", "sort_order": 2}],
            "responsible": None,
            "description": None,
            "colour": "#7dd3fc",
            "copy_template_html": None,
            "sort_order": sort_order,
        }
        for item, sort_order in ((items[1], 5), (items[0], 10))
    ]
    source = json.dumps(browser_payload, ensure_ascii=False, separators=(",", ":"))

    assert mp_backend_module._general_schedule_fingerprint(items) == hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()


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


def test_mp_backend_publish_filters_tasks_to_requested_day(
    db, client, monkeypatch, secure_credential_store
):
    """Publishing one day sends only that day's tasks to MP-Backend."""
    event = create_test_event(db, name="Publish Event")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    create_publish_task(db, event.id, task_type.id, "Session Task", "2026-08-02")
    db.commit()
    acknowledge_current_policy(db, event.id)

    FakeAsyncClient.captured_payloads = []
    FakeAsyncClient.supports_scoped_publish = True
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        f"/api/v1/mp-backend/publish/{event.id}",
        json={"dates": ["2026-08-01"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["tasks_created"] == 1
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["contract_version"] == "2026-07-30"
    assert payload["publish_scope"] == "dates"
    assert payload["dates"] == ["2026-08-01"]
    assert [task["name"] for task in payload["tasks"]] == ["Arrival Task"]


def test_mp_backend_publish_requires_exact_current_policy_acknowledgement(
    db, client, monkeypatch, secure_credential_store
):
    """Publishing fails closed before data crosses the wire without exact consent."""
    event = create_test_event(db, name="Policy-gated publish")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    db.commit()

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "desktop_data_policy_acknowledgement_required"
    assert FakeAsyncClient.captured_payloads == []


def test_mp_backend_policy_supersession_invalidates_local_acknowledgement(
    db, client, monkeypatch, secure_credential_store
):
    """A newly published Server digest invalidates the previous local identity."""
    event = create_test_event(db, name="Superseded policy")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    db.commit()
    acknowledge_current_policy(db, event.id)

    monkeypatch.setattr(FakeAsyncClient, "policy_version", 8)
    monkeypatch.setattr(FakeAsyncClient, "policy_sha256", "c" * 64)
    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 428
    detail = response.json()["detail"]
    assert detail["policy_version"] == 8
    assert detail["policy_sha256"] == "c" * 64
    assert FakeAsyncClient.captured_payloads == []


def test_mp_backend_publish_blocks_unreviewed_legacy_template_field(
    db, client, monkeypatch, secure_credential_store
):
    """Legacy free-form fields remain local until an operator classifies them."""
    event = create_test_event(db, name="Legacy classification")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    template = TaskTemplate(
        machine_name="legacy_notes",
        name="Legacy notes",
        task_type_id=task_type.id,
        fields=[{"id": "notes", "name": "Notes", "type": "text"}],
    )
    db.add(template)
    db.flush()
    task = Task(
        event_id=event.id,
        task_type_id=task_type.id,
        task_template_id=template.id,
        title="Legacy task",
        constraints={"field_values": {"notes": "private note"}},
        optimised={"start_time": 600, "end_time": 660, "location": None},
        final={"start_time": 600, "end_time": 660, "location": None},
        additional={"date": "2026-08-01"},
        is_floating=False,
        is_transfer=False,
    )
    db.add(task)
    db.commit()
    acknowledge_current_policy(db, event.id)

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 409
    assert "reviewed" in response.json()["detail"]
    assert FakeAsyncClient.captured_payloads == []


def test_mp_backend_publish_without_dates_sends_all_tasks(
    db, client, monkeypatch, secure_credential_store
):
    """Publishing without a day subset preserves the existing all-event behaviour."""
    event = create_test_event(db, name="Publish Event")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    create_publish_task(db, event.id, task_type.id, "Session Task", "2026-08-02")
    db.commit()
    acknowledge_current_policy(db, event.id)

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


def test_mp_backend_publish_excludes_unavailable_group_member_and_emits_overnight_data(
    db,
    client,
    monkeypatch,
    secure_credential_store,
):
    """Published group allocations are availability-aware and retain the overnight tail."""
    event = create_test_event(db, name="Overnight Publish")
    configure_mp_backend(event, secure_credential_store)
    event.meta_data = {"schedule_day_range": {"startHour": 6, "endHour": 30}}
    task_type = create_test_task_type(db)
    available = Person(
        event_id=event.id,
        first_name="Ada",
        last_name="Available",
    )
    unavailable = Person(
        event_id=event.id,
        first_name="Una",
        last_name="Unavailable",
    )
    db.add_all([available, unavailable])
    db.flush()
    db.add(
        PersonUnavailability(
            event_id=event.id,
            person_id=unavailable.id,
            starts_at=datetime.fromisoformat("2026-08-02T00:30:00"),
            ends_at=datetime.fromisoformat("2026-08-02T02:00:00"),
        )
    )
    group = Group(
        event_id=event.id,
        name="Night Team",
        meta_data={
            "members": [
                {"type": "person", "id": available.id},
                {"type": "person", "id": unavailable.id},
            ],
        },
    )
    template = TaskTemplate(
        machine_name="overnight_group_test",
        name="Overnight Group Test",
        task_type_id=task_type.id,
        fields=[
            {
                "id": "crew",
                "name": "Crew",
                "type": "persons_list",
                "category": "conditions",
                "purpose": "assignment",
                "visibility": "participant",
                "classification_reviewed": True,
            },
        ],
    )
    db.add_all([group, template])
    db.flush()
    task = Task(
        event_id=event.id,
        task_type_id=task_type.id,
        task_template_id=template.id,
        title="Night Duty",
        constraints={
            "field_values": {"crew": [{"type": "group", "id": group.id}]},
        },
        optimised={},
        final={
            "start_time": 25 * 60,
            "end_time": 26 * 60,
            "field_assignments": {
                "crew": [available.id, unavailable.id],
                "field_Assigned": [available.id, unavailable.id],
            },
        },
        additional={"date": "2026-08-01"},
        is_floating=False,
        is_transfer=False,
    )
    db.add(task)
    db.flush()
    db.add_all(
        [
            Assignment(event_id=event.id, task_id=task.id, person_id=available.id),
            Assignment(event_id=event.id, task_id=task.id, person_id=unavailable.id),
        ],
    )
    db.commit()
    acknowledge_current_policy(db, event.id)

    FakeAsyncClient.captured_payloads = []
    monkeypatch.setattr(mp_backend_module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/api/v1/mp-backend/publish/{event.id}", json={})

    assert response.status_code == 200
    payload = FakeAsyncClient.captured_payloads[0]
    assert payload["event"]["schedule_day_range"] == {"start_hour": 6, "end_hour": 30}
    published_task = payload["tasks"][0]
    assert published_task["start"] == "2026-08-02T01:00:00"
    assert published_task["end"] == "2026-08-02T02:00:00"
    assert "additional" not in published_task
    assert [person["person_id"] for person in published_task["attendees"]] == [available.id]
    assert [person["person_id"] for person in published_task["field_assignments"]["crew"]] == [available.id]
    assert any(
        interval["person_id"] == unavailable.id
        and interval["working_date"] == "2026-08-01"
        and interval["start"] == "2026-08-02T00:30:00"
        for interval in payload["unavailabilities"]
    )


def test_mp_backend_publish_rejects_invalid_date(client, db, secure_credential_store):
    """Invalid day ids are rejected before any external publish call is made."""
    event = create_test_event(db, name="Publish Event")
    configure_mp_backend(event, secure_credential_store)
    db.commit()
    acknowledge_current_policy(db, event.id)

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
    secure_credential_store,
):
    """Older servers must not receive a one-day payload they would full-replace."""
    event = create_test_event(db, name="Publish Event")
    configure_mp_backend(event, secure_credential_store)
    task_type = create_test_task_type(db)
    create_publish_task(db, event.id, task_type.id, "Arrival Task", "2026-08-01")
    db.commit()
    acknowledge_current_policy(db, event.id)

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
    secure_credential_store,
):
    """A successful selected-day retry clears only that day's stale failure."""
    event = create_test_event(db, name="Public Programme")
    configure_mp_backend(event, secure_credential_store)
    view = ScheduleView(event_id=event.id, name="Public", sort_order=0)
    location = Location(
        event_id=event.id,
        name="Main Hall",
        address="1 Parliament Square",
    )
    db.add_all([view, location])
    db.flush()
    db.add_all(
        [
            SessionElement(
                event_id=event.id,
                title="Day One",
                date="2026-08-01",
                start_time="09:00",
                end_time="10:00",
                location_id=location.id,
                responsible_text="Session president",
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
    acknowledge_current_policy(db, event.id)

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
    assert payload["items"][0]["location_name"] == "Main Hall"
    assert payload["items"][0]["location_address"] == "1 Parliament Square"
    assert payload["items"][0]["responsible"] == "Session president"
    db.refresh(state)
    assert state.day_records["2026-08-01"]["publish_failed_at"] is None
    assert state.day_records["2026-08-01"]["failure_message"] is None
    assert state.day_records["2026-08-02"]["failure_message"] == "Another failure."
    assert state.publish_failed_at == "2026-07-12T13:00:00Z"


def test_public_schedule_all_days_publish_sends_full_programme(
    db,
    client,
    monkeypatch,
    secure_credential_store,
):
    """Publishing all days sends one full replacement payload."""
    event = create_test_event(db, name="Public Programme")
    configure_mp_backend(event, secure_credential_store)
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
    acknowledge_current_policy(db, event.id)

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
