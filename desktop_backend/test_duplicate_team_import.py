"""Regression tests for idempotent team/group member imports."""

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.groups import GroupCreate, create_group, update_group, GroupUpdate
from app.core.group_member_resolution import resolve_group_member_person_ids
from app.core.normalizer import (
    Person as FlowPerson,
    Task as FlowTask,
    normalize_flow_input,
)
from app.core.normalizer_optimization import (
    OptimizationPerson,
    OptimizationTask,
    normalize_optimization_input,
)
from app.core.task_payload_normalisation import normalise_task_json_id_lists
from app.models.task_template import TaskTemplate
from app.schemas.masterplan import TaskInstancePayload
from app.api.v1.task_instances import TaskInstanceCreate
from desktop_backend.conftest import (
    create_test_event,
    create_test_person,
    create_test_task_type,
)


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


def test_task_payload_normalisation_preserves_typed_person_and_group_references():
    """Task person fields keep live group references while removing duplicates."""
    payload = {
        "facilitators": [
            {"type": "person", "id": "1"},
            {"type": "group", "id": "10"},
            {"type": "group", "id": 10},
            2,
        ],
    }

    assert normalise_task_json_id_lists(payload) == {
        "facilitators": [
            {"type": "person", "id": 1},
            {"type": "group", "id": 10},
            {"type": "person", "id": 2},
        ],
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


def test_group_api_supports_nested_group_members_and_deduplicates_them(db):
    """Groups may include people and other groups without duplicate entries."""
    event = create_test_event(db, name="Nested groups event")
    core = asyncio.run(
        create_group(
            GroupCreate(
                name="Core Team",
                members=[
                    {"type": "person", "id": 2},
                    {"type": "person", "id": 3},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    orga = asyncio.run(
        create_group(
            GroupCreate(
                name="OrgaTeam",
                members=[
                    {"type": "person", "id": 1},
                    {"type": "person", "id": 1},
                    {"type": "group", "id": core.id},
                    {"type": "group", "id": str(core.id)},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    assert orga.members == [
        {"type": "person", "id": 1},
        {"type": "group", "id": core.id},
    ]


def test_group_api_keeps_existing_person_only_payloads_compatible(db):
    """Legacy scalar person IDs are stored as typed person members."""
    event = create_test_event(db, name="Legacy group event")

    created = asyncio.run(
        create_group(
            GroupCreate(name="Legacy Team", members=[1, "2", 1]),
            event_id=event.id,
            db=db,
        ),
    )

    assert created.members == [
        {"type": "person", "id": 1},
        {"type": "person", "id": 2},
    ]


def test_group_api_blocks_self_reference(db):
    """A group cannot include itself."""
    event = create_test_event(db, name="Self reference event")
    created = asyncio.run(
        create_group(
            GroupCreate(name="OrgaTeam", members=[]),
            event_id=event.id,
            db=db,
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_group(
                created.id,
                GroupUpdate(members=[{"type": "group", "id": created.id}]),
                event_id=event.id,
                db=db,
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "This would create a circular group reference."


def test_group_api_blocks_circular_references(db):
    """Saving a group cannot introduce a circular included-group chain."""
    event = create_test_event(db, name="Circular reference event")
    core = asyncio.run(
        create_group(
            GroupCreate(name="Core Team", members=[]),
            event_id=event.id,
            db=db,
        ),
    )
    orga = asyncio.run(
        create_group(
            GroupCreate(
                name="OrgaTeam",
                members=[{"type": "group", "id": core.id}],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_group(
                core.id,
                GroupUpdate(members=[{"type": "group", "id": orga.id}]),
                event_id=event.id,
                db=db,
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "This would create a circular group reference."


def test_group_api_blocks_included_groups_from_other_events(db):
    """Included groups must belong to the same event as the saved group."""
    event = create_test_event(db, name="Primary event")
    other_event = create_test_event(db, name="Other event")
    other_group = asyncio.run(
        create_group(
            GroupCreate(name="Other Team", members=[]),
            event_id=other_event.id,
            db=db,
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            create_group(
                GroupCreate(
                    name="OrgaTeam",
                    members=[{"type": "group", "id": other_group.id}],
                ),
                event_id=event.id,
                db=db,
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Included group not found in this event."


def _create_person_field_template(db, task_type_id: int) -> TaskTemplate:
    """Create a template with time and persons fields for normaliser tests."""
    template = TaskTemplate(
        machine_name="team_assignment_template",
        name="Team Assignment Template",
        task_type_id=task_type_id,
        fields=[
            {
                "id": "people",
                "name": "People",
                "type": "persons_list",
                "category": "conditions",
            },
            {
                "id": "field_time_test",
                "name": "Time",
                "type": "start_end_time",
                "category": "conditions",
            },
        ],
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def _create_nested_group_fixture(db):
    """Create people and nested groups for live propagation assertions."""
    event = create_test_event(db, name="Live group propagation event")
    alice = create_test_person(db, event.id, "Alice", "Core")
    bob = create_test_person(db, event.id, "Bob", "Nested")
    clara = create_test_person(db, event.id, "Clara", "Later")

    core = asyncio.run(
        create_group(
            GroupCreate(name="Core Team", members=[{"type": "person", "id": bob.id}]),
            event_id=event.id,
            db=db,
        ),
    )
    orga = asyncio.run(
        create_group(
            GroupCreate(
                name="OrgaTeam",
                members=[
                    {"type": "person", "id": alice.id},
                    {"type": "group", "id": core.id},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )
    return event, alice, bob, clara, core, orga


def test_group_resolution_propagates_when_group_membership_changes(db):
    """Resolving a stored group reference uses the group's current members."""
    event, alice, bob, clara, core, orga = _create_nested_group_fixture(db)
    task_assignment = [{"type": "group", "id": orga.id}]

    resolved, warnings = resolve_group_member_person_ids(
        task_assignment,
        db,
        {alice.id, bob.id, clara.id},
        event.id,
    )
    assert warnings == []
    assert resolved == [alice.id, bob.id]

    asyncio.run(
        update_group(
            core.id,
            GroupUpdate(
                members=[
                    {"type": "person", "id": bob.id},
                    {"type": "person", "id": clara.id},
                ],
            ),
            event_id=event.id,
            db=db,
        ),
    )

    resolved_after_change, warnings_after_change = resolve_group_member_person_ids(
        task_assignment,
        db,
        {alice.id, bob.id, clara.id},
        event.id,
    )
    assert warnings_after_change == []
    assert resolved_after_change == [alice.id, bob.id, clara.id]


def test_group_resolution_ignores_missing_groups_without_crashing(db):
    """Deleted or missing group references are ignored with a warning."""
    event = create_test_event(db, name="Missing group event")
    alice = create_test_person(db, event.id, "Alice", "Known")

    resolved, warnings = resolve_group_member_person_ids(
        [{"type": "person", "id": alice.id}, {"type": "group", "id": 404}],
        db,
        {alice.id},
        event.id,
    )

    assert resolved == [alice.id]
    assert warnings == ["Group 404 no longer exists."]


def test_flow_normaliser_resolves_live_group_references(db):
    """Flow-check input resolves task group references to current people."""
    event, alice, bob, _clara, _core, orga = _create_nested_group_fixture(db)
    task_type = create_test_task_type(db, "Meeting")
    template = _create_person_field_template(db, task_type.id)

    normalised = normalize_flow_input(
        tasks=[
            FlowTask(
                id=100,
                template_id=template.id,
                name="Briefing",
                task_type_id=task_type.id,
                event_id=event.id,
                field_values={
                    "people": [{"type": "group", "id": orga.id}],
                    "field_time_test": {"start": "09:00", "end": "10:00"},
                },
            )
        ],
        persons=[
            FlowPerson(id=alice.id, first_name="Alice", last_name="Core"),
            FlowPerson(id=bob.id, first_name="Bob", last_name="Nested"),
        ],
        locations=[],
        capabilities=[],
        db=db,
    )

    assert normalised.errors == []
    assert normalised.tasks[0].preassigned_person_ids == [alice.id, bob.id]


def test_optimisation_normaliser_resolves_live_group_references(db):
    """Optimisation input resolves task group references at runtime."""
    event, alice, bob, _clara, _core, orga = _create_nested_group_fixture(db)
    task_type = create_test_task_type(db, "Workshop")
    template = _create_person_field_template(db, task_type.id)

    normalised = normalize_optimization_input(
        tasks=[
            OptimizationTask(
                id=100,
                name="Briefing",
                task_type_id=task_type.id,
                template_id=template.id,
                event_id=event.id,
                start_time=9 * 60,
                end_time=10 * 60,
                field_values={"people": [{"type": "group", "id": orga.id}]},
            )
        ],
        persons=[
            OptimizationPerson(id=alice.id, first_name="Alice", last_name="Core"),
            OptimizationPerson(id=bob.id, first_name="Bob", last_name="Nested"),
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={task_type.id: 1.0},
        db=db,
        event_id=event.id,
    )

    assert normalised.errors == []
    assert normalised.tasks[0].preassigned_person_ids == [alice.id, bob.id]
