"""Regression tests for idempotent team/group member imports."""

import asyncio

from app.api.v1.groups import GroupCreate, create_group, update_group, GroupUpdate
from app.core.task_payload_normalisation import normalise_task_json_id_lists
from app.schemas.masterplan import TaskInstancePayload
from app.api.v1.task_instances import TaskInstanceCreate
from desktop_backend.conftest import create_test_event


def test_task_payload_normalisation_deduplicates_person_id_lists_without_changing_capabilities():
    """Duplicate person IDs are removed while capability quantity objects survive."""
    payload = {
        "direct_people": [1, 2, 1, "2", 3],
        "required_capabilities": [
            {"id": 10, "quantity": 2},
            {"id": 10, "quantity": 3},
        ],
        "nested": {"assigned_persons": [4, 4, 5]},
    }

    assert normalise_task_json_id_lists(payload) == {
        "direct_people": [1, 2, 3],
        "required_capabilities": [
            {"id": 10, "quantity": 2},
            {"id": 10, "quantity": 3},
        ],
        "nested": {"assigned_persons": [4, 5]},
    }


def test_task_instance_create_schema_deduplicates_reimported_group_members():
    """Task instance create payloads store unique person IDs after group re-import."""
    payload = TaskInstanceCreate(
        event_id=1,
        template_id=1,
        task_type_id=1,
        date="2026-08-01",
        field_values={"facilitators": [1, 3, 1, 2, 3]},
    )

    assert payload.field_values == {"facilitators": [1, 3, 2]}


def test_finalise_payload_schema_deduplicates_visible_assignments():
    """Finalise payloads cannot create duplicate assignment rows from repeated IDs."""
    payload = TaskInstancePayload(
        id=100,
        event_id=1,
        date="2026-08-01",
        field_values={"facilitators": [1, 3, 1, 2]},
        final={"assigned_persons": [1, 1, 2]},
    )

    assert payload.field_values == {"facilitators": [1, 3, 2]}
    assert payload.final == {"assigned_persons": [1, 2]}


def test_group_api_create_and_update_are_idempotent_for_duplicate_person_members(db):
    """Backend group writes skip duplicate person members instead of storing them."""
    event = create_test_event(db, name="Group import event")

    created = asyncio.run(
        create_group(
            GroupCreate(
                name="Team A",
                members=[
                    {"type": "person", "id": 1},
                    {"type": "person", "id": 1},
                    {"type": "person", "id": "2"},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    assert created.members == [
        {"type": "person", "id": 1},
        {"type": "person", "id": 2},
    ]

    updated = asyncio.run(
        update_group(
            created.id,
            GroupUpdate(
                members=[
                    {"type": "person", "id": 2},
                    {"type": "person", "id": 1},
                    {"type": "person", "id": 2},
                    {"type": "person", "id": 3},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    assert updated.members == [
        {"type": "person", "id": 2},
        {"type": "person", "id": 1},
        {"type": "person", "id": 3},
    ]
