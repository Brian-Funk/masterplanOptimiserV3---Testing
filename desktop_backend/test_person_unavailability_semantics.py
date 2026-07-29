"""Regression tests for UI-entered person unavailability semantics."""

from app.core.normalizer import (
    Capability as FlowCapability,
    Location as FlowLocation,
    Person as FlowPerson,
    Task as FlowTask,
    normalize_flow_input,
)
from app.core.normalizer_optimization import (
    OptimizationCapability,
    OptimizationLocation,
    OptimizationPerson,
    OptimizationTask,
    normalize_optimization_input,
)
from app.core.group_member_resolution import resolve_group_assignment_for_task
from app.models.group import Group
from app.models.task_template import TaskTemplate
from desktop_backend.conftest import create_test_event, create_test_task_type
from fatigue_optimizer import OptimizationConfig, optimize_with_fatigue
from flow_checker import NormPerson, NormTask, NormalizedFlowInput, check_flow


def _fast_config():
    return OptimizationConfig(
        scale=100,
        break_threshold_min=30,
        break_effect=-3.0,
        max_time_seconds=10.0,
    )


def _create_capability_template(db):
    create_test_task_type(db, name="Unavailability task", task_type_id=31)
    template = TaskTemplate(
        machine_name="unavailability_capability_template",
        name="Unavailability Capability Template",
        task_type_id=31,
        fields=[
            {"id": "time", "name": "Time", "type": "start_end_time", "category": "conditions"},
            {"id": "needed", "name": "Needed", "type": "capabilities_list", "category": "conditions"},
        ],
        is_floating=False,
        is_transfer=False,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def _create_group(db, event_id, person_id):
    group = Group(
        event_id=event_id,
        name="Availability group",
        meta_data={"members": [{"type": "person", "id": person_id}]},
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def test_group_resolution_does_not_shift_an_adjacent_day_interval(db):
    event = create_test_event(db, name="Adjacent-day availability")
    group = _create_group(db, event.id, 7)

    resolved = resolve_group_assignment_for_task(
        [{"type": "group", "id": group.id}],
        db,
        {7},
        event_id=event.id,
        person_unavailable_intervals={7: [(1980, 2040)]},
        task_start=540,
        task_end=600,
    )

    assert resolved.person_ids == [7]
    assert resolved.excluded_persons == []


def test_group_resolution_uses_linear_overnight_coordinates(db):
    event = create_test_event(db, name="Overnight availability")
    group = _create_group(db, event.id, 7)

    resolved = resolve_group_assignment_for_task(
        [{"type": "group", "id": group.id}],
        db,
        {7},
        event_id=event.id,
        person_unavailable_intervals={7: [(1500, 1560)]},
        task_start=1515,
        task_end=1545,
    )

    assert resolved.person_ids == []
    assert [item.person_id for item in resolved.excluded_persons] == [7]


def test_flow_api_scopes_one_off_unavailability_to_selected_day(db, client):
    template = _create_capability_template(db)
    payload = {
        "tasks": [
            {
                "id": 101,
                "name": "Evening Meeting",
                "template_id": template.id,
                "task_type_id": 31,
                "location_id": 1,
                "field_values": {
                    "time": {"start": "18:30", "end": "19:30"},
                    "needed": [{"id": 1, "quantity": 1}],
                },
            }
        ],
        "persons": [
            {
                "id": 1,
                "first_name": "Ben",
                "last_name": "Evening",
                "home_location_id": 1,
                "capabilities": ["staff"],
                "unavailabilities": [
                    {
                        "starts_at": "2026-06-10T18:00",
                        "ends_at": "2026-06-10T20:00",
                    }
                ],
            }
        ],
        "locations": [{"id": 1, "name": "Room A"}],
        "capabilities": [{"id": 1, "machine_name": "staff", "name": "Staff"}],
    }

    blocked = client.post(
        "/api/v1/flow/check",
        json={**payload, "working_day_date": "2026-06-10"},
    )
    available = client.post(
        "/api/v1/flow/check",
        json={**payload, "working_day_date": "2026-06-11"},
    )

    assert blocked.status_code == 200
    assert blocked.json()["feasible"] is False
    assert any("Evening Meeting" in error for error in blocked.json()["errors"])
    assert available.status_code == 200
    available_payload = available.json()
    assert available_payload["errors"] == []
    assert available_payload["feasible"] is True
    assert available_payload["diagnostics"]["schema_version"] == 1
    assert available_payload["diagnostics"]["status"] == "feasible"
    assert available_payload["diagnostics"]["checked_scope"] == "full"
    assert available_payload["diagnostics"]["issues"] == []


def test_optimiser_does_not_select_unavailable_capability_provider(db):
    normalized = NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=["staff"],
                unavailable_intervals=[(1080, 1200)],
            ),
            NormPerson(
                id=2,
                home_location_id=1,
                capabilities=["staff"],
                unavailable_intervals=[],
            ),
        ],
        tasks=[
            NormTask(
                id=201,
                name="Staffed Meeting",
                location_id=1,
                start_time=1110,
                end_time=1170,
                requirements={"staff": 1},
            )
        ],
        transfers=[],
        floating_tasks=[],
        errors=[],
    )

    result = optimize_with_fatigue(normalized, _fast_config())

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.capability_assignments[(201, "staff")] == [2]


def test_optimiser_allows_available_capability_provider(db):
    normalized = NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=["staff"],
                unavailable_intervals=[],
            )
        ],
        tasks=[
            NormTask(
                id=202,
                name="Other Day Meeting",
                location_id=1,
                start_time=1110,
                end_time=1170,
                requirements={"staff": 1},
            )
        ],
        transfers=[],
        floating_tasks=[],
        errors=[],
    )

    result = optimize_with_fatigue(normalized, _fast_config())

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.capability_assignments[(202, "staff")] == [1]


def test_flow_checker_rejects_unavailability_in_middle_of_long_task():
    input_data = NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=["staff"],
                unavailable_intervals=[(540, 545)],
            )
        ],
        tasks=[
            NormTask(
                id=301,
                name="Long Meeting",
                location_id=1,
                start_time=480,
                end_time=600,
                requirements={"staff": 1},
            )
        ],
        transfers=[],
        floating_tasks=[],
        errors=[],
    )

    errors = check_flow(input_data, max_time_seconds=5)

    assert errors
    assert any("Long Meeting" in error and "available" in error for error in errors)


def test_flow_and_optimisation_normalizers_match_boundary_unavailability():
    unavailabilities = [
        {
            "starts_at": "2026-06-11T01:00",
            "ends_at": "2026-06-11T02:00",
        },
    ]
    optimisation = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Night",
                last_name="Unavailable",
                unavailabilities=unavailabilities,
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
        working_day_boundary_offset_hour=4,
    )
    flow = normalize_flow_input(
        tasks=[],
        persons=[
            FlowPerson(
                id=1,
                first_name="Night",
                last_name="Unavailable",
                unavailabilities=unavailabilities,
            )
        ],
        locations=[FlowLocation(id=1, name="Room A")],
        capabilities=[FlowCapability(id=1, machine_name="staff", name="Staff")],
        working_day_date="2026-06-10",
        working_day_boundary_offset_hour=4,
    )

    assert optimisation.persons[0].unavailable_intervals == [(1500, 1560)]
    assert flow.persons[0].unavailable_intervals == [(1500, 1560)]
