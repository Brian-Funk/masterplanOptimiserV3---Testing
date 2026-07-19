"""Regression tests for desktop General Schedule APIs."""

from desktop_backend.conftest import (
    create_test_event,
    create_test_location,
    create_test_person,
)


def _create_team(client, event_id: int) -> int:
    response = client.post(
        f"/api/v1/general-schedule/teams?event_id={event_id}",
        json={"name": "Delegates"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_type(client, event_id: int) -> tuple[int, str]:
    colour = "#a5b4fc"
    response = client.post(
        f"/api/v1/general-schedule/session-element-types?event_id={event_id}",
        json={
            "name": "Committee",
            "description": "Committee sessions",
            "colour": colour,
            "copy_template_html": "<b>{title}</b>",
        },
    )
    assert response.status_code == 201
    return response.json()["id"], colour


def _create_view(client, event_id: int, name: str = "Delegates") -> int:
    response = client.post(
        f"/api/v1/general-schedule/schedule-views?event_id={event_id}",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_session_element_writes_ignore_legacy_hidden_fields(db, client):
    event = create_test_event(db)
    location = create_test_location(db, event.id, name="Room A")
    person = create_test_person(db, event.id, first_name="Anna", last_name="Muller")
    team_id = _create_team(client, event.id)
    view_id = _create_view(client, event.id)
    type_id, type_colour = _create_type(client, event.id)

    create_payload = {
        "title": "Opening Briefing",
        "date": "2026-08-01",
        "start_time": "09:00",
        "end_time": "10:00",
        "session_element_type_id": type_id,
        "location_id": location.id,
        "responsible_person_id": person.id,
        "responsible_text": "Desk",
        "location_text": "Legacy free text",
        "location_note": "Legacy note",
        "attendee_team_ids": [team_id],
        "schedule_view_ids": [view_id],
        "visibility": "internal",
        "description": "Bring laptops.",
        "category": "Legacy category",
        "colour": "#ff0000",
    }
    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json=create_payload,
    )
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["visibility"] == "public"
    assert created_data["colour"] == type_colour
    assert created_data["location_text"] is None
    assert created_data["location_note"] is None
    assert created_data["category"] is None
    assert created_data["schedule_view_ids"] == [view_id]

    updated = client.put(
        f"/api/v1/general-schedule/session-elements/{created_data['id']}?event_id={event.id}",
        json={
            "location_text": "Should still be ignored",
            "location_note": "Should still be ignored",
            "visibility": "internal",
            "category": "Still ignored",
            "colour": "#00ff00",
        },
    )
    assert updated.status_code == 200
    updated_data = updated.json()
    assert updated_data["visibility"] == "public"
    assert updated_data["colour"] == type_colour
    assert updated_data["location_text"] is None
    assert updated_data["location_note"] is None
    assert updated_data["category"] is None
    assert updated_data["schedule_view_ids"] == [view_id]

    duplicate = client.post(
        f"/api/v1/general-schedule/session-elements/{created_data['id']}/duplicate?event_id={event.id}",
    )
    assert duplicate.status_code == 200
    duplicate_data = duplicate.json()
    assert duplicate_data["visibility"] == "public"
    assert duplicate_data["colour"] == type_colour
    assert duplicate_data["location_text"] is None
    assert duplicate_data["location_note"] is None
    assert duplicate_data["category"] is None
    assert duplicate_data["schedule_view_ids"] == [view_id]

    copied = client.post(
        f"/api/v1/general-schedule/session-elements/copy?event_id={event.id}",
        json={"element_ids": [created_data["id"]], "target_dates": ["2026-08-02"]},
    )
    assert copied.status_code == 200
    copied_data = copied.json()[0]
    assert copied_data["visibility"] == "public"
    assert copied_data["colour"] == type_colour
    assert copied_data["location_text"] is None
    assert copied_data["location_note"] is None
    assert copied_data["category"] is None
    assert copied_data["schedule_view_ids"] == [view_id]


def test_session_element_allows_no_target_audience_or_schedule_view(db, client):
    event = create_test_event(db)
    type_id, _ = _create_type(client, event.id)

    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Unpublished briefing",
            "date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "session_element_type_id": type_id,
            "attendee_team_ids": [],
            "schedule_view_ids": [],
        },
    )

    assert created.status_code == 201
    data = created.json()
    assert data["attendee_team_ids"] == []
    assert data["schedule_view_ids"] == []


def test_schedule_view_validation_and_delete_cleanup(db, client):
    event = create_test_event(db)
    type_id, _ = _create_type(client, event.id)
    view_id = _create_view(client, event.id, name="Officials")

    missing = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Invalid view",
            "date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "session_element_type_id": type_id,
            "schedule_view_ids": [999],
        },
    )
    assert missing.status_code == 400
    assert "Schedule view not found" in missing.json()["detail"]

    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Officials briefing",
            "date": "2026-08-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "session_element_type_id": type_id,
            "schedule_view_ids": [view_id],
        },
    )
    assert created.status_code == 201

    deleted = client.delete(
        f"/api/v1/general-schedule/schedule-views/{view_id}?event_id={event.id}",
    )
    assert deleted.status_code == 204

    elements = client.get(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
    )
    assert elements.status_code == 200
    assert elements.json()[0]["schedule_view_ids"] == []


def test_session_element_type_delete_requires_no_references(db, client):
    event = create_test_event(db)
    team_id = _create_team(client, event.id)
    used_type_id, _ = _create_type(client, event.id)
    unused_type_response = client.post(
        f"/api/v1/general-schedule/session-element-types?event_id={event.id}",
        json={"name": "Breaks", "colour": "#86efac"},
    )
    assert unused_type_response.status_code == 201
    unused_type_id = unused_type_response.json()["id"]

    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Opening Briefing",
            "date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "session_element_type_id": used_type_id,
            "attendee_team_ids": [team_id],
        },
    )
    assert created.status_code == 201

    blocked = client.delete(
        f"/api/v1/general-schedule/session-element-types/{used_type_id}?event_id={event.id}",
    )
    assert blocked.status_code == 400
    assert "used by existing Session Elements" in blocked.json()["detail"]

    deleted = client.delete(
        f"/api/v1/general-schedule/session-element-types/{unused_type_id}?event_id={event.id}",
    )
    assert deleted.status_code == 204

    remaining = client.get(
        f"/api/v1/general-schedule/session-element-types?event_id={event.id}",
    )
    assert remaining.status_code == 200
    assert unused_type_id not in {row["id"] for row in remaining.json()}


def test_session_element_type_can_delete_only_type_when_unused(db, client):
    event = create_test_event(db)
    type_id, _ = _create_type(client, event.id)

    deleted = client.delete(
        f"/api/v1/general-schedule/session-element-types/{type_id}?event_id={event.id}",
    )
    assert deleted.status_code == 204

    remaining = client.get(
        f"/api/v1/general-schedule/session-element-types?event_id={event.id}",
    )
    assert remaining.status_code == 200
    assert remaining.json() == []


def test_bulk_update_replaces_public_views_and_audience_atomically(db, client):
    """Bulk editing applies one view and audience selection to every chosen item."""
    event = create_test_event(db)
    type_id, _ = _create_type(client, event.id)
    team_id = _create_team(client, event.id)
    view_id = _create_view(client, event.id)
    element_ids = []
    for index in range(2):
        response = client.post(
            f"/api/v1/general-schedule/session-elements?event_id={event.id}",
            json={
                "title": f"Session {index + 1}",
                "date": "2026-08-01",
                "start_time": f"{9 + index:02d}:00",
                "end_time": f"{10 + index:02d}:00",
                "session_element_type_id": type_id,
            },
        )
        assert response.status_code == 201
        element_ids.append(response.json()["id"])

    updated = client.patch(
        f"/api/v1/general-schedule/session-elements/bulk?event_id={event.id}",
        json={
            "element_ids": element_ids,
            "schedule_view_ids": [view_id],
            "attendee_team_ids": [team_id],
        },
    )

    assert updated.status_code == 200
    assert [item["id"] for item in updated.json()] == element_ids
    assert all(item["schedule_view_ids"] == [view_id] for item in updated.json())
    assert all(item["attendee_team_ids"] == [team_id] for item in updated.json())

    rejected = client.patch(
        f"/api/v1/general-schedule/session-elements/bulk?event_id={event.id}",
        json={
            "element_ids": [element_ids[0], 999999],
            "schedule_view_ids": [],
        },
    )
    assert rejected.status_code == 404
    reloaded = client.get(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
    ).json()
    assert all(item["schedule_view_ids"] == [view_id] for item in reloaded)


def test_copy_elements_preserves_after_midnight_working_day_slots(db, client):
    """Copying to a working day stores its after-midnight item on the next date."""
    event = create_test_event(db)
    event.meta_data = {
        "schedule_day_range": {"startHour": 6, "endHour": 30},
    }
    db.commit()
    type_id, _ = _create_type(client, event.id)
    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Night Session",
            "date": "2026-08-02",
            "start_time": "01:00",
            "end_time": "02:00",
            "session_element_type_id": type_id,
        },
    )
    assert created.status_code == 201

    copied = client.post(
        f"/api/v1/general-schedule/session-elements/copy?event_id={event.id}",
        json={
            "element_ids": [created.json()["id"]],
            "target_dates": ["2026-08-03"],
        },
    )

    assert copied.status_code == 200
    assert copied.json()[0]["date"] == "2026-08-04"
    assert copied.json()[0]["start_time"] == "01:00"


def test_bulk_update_supports_opt_in_fields_and_assignment_operations(db, client):
    event = create_test_event(db)
    first_type_id, _ = _create_type(client, event.id)
    second_type = client.post(
        f"/api/v1/general-schedule/session-element-types?event_id={event.id}",
        json={"name": "Plenary", "colour": "#86efac"},
    ).json()
    first_view = _create_view(client, event.id, "Delegates")
    second_view = _create_view(client, event.id, "Officials")
    team_id = _create_team(client, event.id)
    location = create_test_location(db, event.id, name="Room B")
    element_ids = []
    for index in range(2):
        created = client.post(
            f"/api/v1/general-schedule/session-elements?event_id={event.id}",
            json={
                "title": f"Item {index}",
                "date": "2026-08-01",
                "start_time": f"{9 + index:02d}:00",
                "end_time": f"{10 + index:02d}:00",
                "session_element_type_id": first_type_id,
                "schedule_view_ids": [first_view],
            },
        )
        element_ids.append(created.json()["id"])

    updated = client.patch(
        f"/api/v1/general-schedule/session-elements/bulk?event_id={event.id}",
        json={
            "element_ids": element_ids,
            "session_element_type_id": second_type["id"],
            "location_id": location.id,
            "working_date": "2026-08-02",
            "shift_minutes": 15,
            "schedule_view_change": {"operation": "add", "ids": [second_view]},
            "attendee_team_change": {"operation": "add", "ids": [team_id]},
        },
    )

    assert updated.status_code == 200
    assert [item["start_time"] for item in updated.json()] == ["09:15", "10:15"]
    assert all(item["date"] == "2026-08-02" for item in updated.json())
    assert all(item["session_element_type_id"] == second_type["id"] for item in updated.json())
    assert all(item["location_id"] == location.id for item in updated.json())
    assert all(item["schedule_view_ids"] == [first_view, second_view] for item in updated.json())
    assert all(item["attendee_team_ids"] == [team_id] for item in updated.json())


def test_bulk_update_is_atomic_and_rejects_cross_event_references(db, client):
    event = create_test_event(db, name="First")
    other_event = create_test_event(db, name="Second")
    type_id, _ = _create_type(client, event.id)
    foreign_view = _create_view(client, other_event.id, "Foreign")
    created = client.post(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}",
        json={
            "title": "Opening",
            "date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "session_element_type_id": type_id,
        },
    ).json()

    rejected = client.patch(
        f"/api/v1/general-schedule/session-elements/bulk?event_id={event.id}",
        json={
            "element_ids": [created["id"]],
            "shift_minutes": 30,
            "schedule_view_change": {"operation": "add", "ids": [foreign_view]},
        },
    )

    assert rejected.status_code == 400
    unchanged = client.get(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}"
    ).json()[0]
    assert unchanged["start_time"] == "09:00"
    assert unchanged["schedule_view_ids"] == []


def test_bulk_create_is_transactional(db, client):
    event = create_test_event(db)
    type_id, _ = _create_type(client, event.id)
    response = client.post(
        f"/api/v1/general-schedule/session-elements/bulk-create?event_id={event.id}",
        json={
            "items": [
                {
                    "title": "Valid",
                    "date": "2026-08-01",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "session_element_type_id": type_id,
                },
                {
                    "title": "Invalid",
                    "date": "2026-08-01",
                    "start_time": "11:00",
                    "end_time": "10:00",
                    "session_element_type_id": type_id,
                },
            ]
        },
    )

    assert response.status_code == 400
    remaining = client.get(
        f"/api/v1/general-schedule/session-elements?event_id={event.id}"
    )
    assert remaining.json() == []
