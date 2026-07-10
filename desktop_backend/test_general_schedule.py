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


def test_session_element_writes_ignore_legacy_hidden_fields(db, client):
    event = create_test_event(db)
    location = create_test_location(db, event.id, name="Room A")
    person = create_test_person(db, event.id, first_name="Anna", last_name="Muller")
    team_id = _create_team(client, event.id)
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
