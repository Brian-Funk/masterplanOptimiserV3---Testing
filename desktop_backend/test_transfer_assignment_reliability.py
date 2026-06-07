"""Regression tests for transfer passenger assignment and movement reliability."""

from app.api.v1.task_instances import TaskInstanceCreate, _derive_template_flags
from app.core.normalizer import (
    Capability,
    Location,
    Person,
    Task,
    normalize_flow_input,
)
from app.core.normalizer_optimization import (
    OptimizationCapability,
    OptimizationLocation,
    OptimizationPerson,
    OptimizationTask,
    normalize_optimization_input,
)
from app.models.task_template import TaskTemplate
from desktop_backend.conftest import create_test_event, create_test_task_type
from fatigue_optimizer import OptimizationConfig, optimize_with_fatigue
from flow_checker import (
    NormPerson,
    NormTask,
    NormTransfer,
    NormalizedFlowInput,
    check_flow,
)


def _fast_config():
    """Return a deterministic low-timeout optimiser config for transfer regressions."""
    return OptimizationConfig(
        scale=100,
        break_threshold_min=30,
        break_effect=-3.0,
        max_time_seconds=10.0,
    )


def _assert_solved(result):
    """Assert that optimisation found a usable solution."""
    assert result.status in {"OPTIMAL", "FEASIBLE"}, (
        f"Expected solver success, got {result.status}: {result.errors}"
    )


def _create_transfer_template(db, task_type_id: int, *, machine_name: str = "transfer_template") -> TaskTemplate:
    """Create a transfer template with driver, dynamic passenger, and route fields."""
    template = TaskTemplate(
        machine_name=machine_name,
        name="Transfer Template",
        task_type_id=task_type_id,
        fields=[
            {"id": "field_time", "name": "Time", "type": "start_end_time"},
            {"id": "field_start_location", "name": "From", "type": "start_location"},
            {"id": "field_end_location", "name": "To", "type": "end_location"},
            {"id": "field_driver", "name": "Lead Driver", "type": "persons_list"},
            {"id": "field_dynamic_allocation", "name": "Dynamic passengers", "type": "number"},
            {"id": "field_transferees", "name": "Passengers", "type": "transferee"},
        ],
        is_floating=False,
        is_transfer=True,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def test_optimisation_normaliser_locks_transfer_persons_list_passengers(db):
    """Transfer persons_list values become locked passengers and field assignments."""
    create_test_task_type(db, name="Transfer", task_type_id=1)
    template = _create_transfer_template(db, 1)

    result = normalize_optimization_input(
        tasks=[
            OptimizationTask(
                id=41,
                name="Hotel to venue",
                task_type_id=1,
                template_id=template.id,
                location_id=1,
                is_transfer=False,
                field_values={
                    "field_time": {"start": "10:30", "end": "11:00"},
                    "field_start_location": 1,
                    "field_end_location": 2,
                    "field_driver": [{"type": "person", "id": 1}],
                    "field_dynamic_allocation": "2",
                },
            )
        ],
        persons=[
            OptimizationPerson(id=1, first_name="Elena", last_name="Macura", home_location_id=1),
            OptimizationPerson(id=2, first_name="Maria", last_name="Amvrosova", home_location_id=1),
        ],
        locations=[
            OptimizationLocation(id=1, name="Hotel"),
            OptimizationLocation(id=2, name="Venue"),
        ],
        capabilities=[],
        task_type_fatigue_map={1: 1.0},
        db=db,
        event_id=1,
    )

    assert result.errors == []
    assert len(result.transfers) == 1
    transfer = result.transfers[0]
    assert transfer.locked_person_ids == [1]
    assert transfer.person_field_assignments == {"field_driver": [1]}
    assert transfer.optional_capacity_slots == 2
    assert transfer.capacity == 3


def test_flow_normaliser_uses_template_transfer_flag_when_instance_flag_is_stale(db):
    """Template is_transfer metadata wins over a stale task instance flag."""
    event = create_test_event(db)
    create_test_task_type(db, name="Transfer", task_type_id=1)
    template = _create_transfer_template(db, 1)

    result = normalize_flow_input(
        tasks=[
            Task(
                id=41,
                event_id=event.id,
                name="Hotel to venue",
                task_type_id=1,
                template_id=template.id,
                location_id=1,
                is_transfer=False,
                field_values={
                    "field_time": {"start": "10:30", "end": "11:00"},
                    "field_start_location": 1,
                    "field_end_location": 2,
                    "field_driver": [1],
                    "field_dynamic_allocation": "",
                },
            )
        ],
        persons=[Person(id=1, first_name="Elena", last_name="Macura", home_location_id=1)],
        locations=[Location(id=1, name="Hotel"), Location(id=2, name="Venue")],
        capabilities=[],
        db=db,
    )

    assert result.errors == []
    assert len(result.transfers) == 1
    assert result.transfers[0].locked_person_ids == [1]
    assert result.transfers[0].optional_capacity_slots == 0
    assert result.transfers[0].capacity == 1
    assert result.tasks == []


def test_invalid_dynamic_allocation_is_reported(db):
    """Invalid transfer capacity values are validation errors, not silent capacity guesses."""
    event = create_test_event(db)
    create_test_task_type(db, name="Transfer", task_type_id=1)
    template = _create_transfer_template(db, 1)

    result = normalize_flow_input(
        tasks=[
            Task(
                id=41,
                event_id=event.id,
                name="Hotel to venue",
                task_type_id=1,
                template_id=template.id,
                location_id=1,
                field_values={
                    "field_time": {"start": "10:30", "end": "11:00"},
                    "field_start_location": 1,
                    "field_end_location": 2,
                    "field_driver": [1],
                    "field_dynamic_allocation": "two",
                },
            )
        ],
        persons=[Person(id=1, first_name="Elena", last_name="Macura", home_location_id=1)],
        locations=[Location(id=1, name="Hotel"), Location(id=2, name="Venue")],
        capabilities=[],
        db=db,
    )

    assert any("invalid dynamic allocation" in error for error in result.errors)


def test_task_instance_create_derives_transfer_flag_from_template(db):
    """Creating an instance without flags stores transfer metadata from the template."""
    create_test_task_type(db, name="Transfer", task_type_id=1)
    template = _create_transfer_template(db, 1)
    payload = TaskInstanceCreate(
        name="Hotel to venue",
        event_id=1,
        template_id=template.id,
        task_type_id=1,
        date="2026-08-01",
        field_values={},
    )

    is_floating, is_transfer = _derive_template_flags(
        db,
        payload.template_id,
        payload.is_floating,
        payload.is_transfer,
    )

    assert is_floating is False
    assert is_transfer is True


def test_optimiser_locks_transfer_driver_and_moves_dynamic_passenger():
    """A locked driver boards the transfer and dynamic capacity moves a later assigned person."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=2, capabilities=[], home_location_id=1, unavailable_intervals=[]),
    ]
    transfers = [
        NormTransfer(
            id=41,
            from_location_id=1,
            to_location_id=2,
            depart_time=540,
            arrive_time=570,
            capacity=2,
            requirements={},
            optional_capacity_slots=1,
            locked_person_ids=[1],
            person_field_assignments={"field_driver": [1]},
            transferee_field_id="field_transferees",
        )
    ]
    tasks = [
        NormTask(
            id=50,
            name="Venue preparation",
            location_id=2,
            start_time=600,
            end_time=660,
            requirements={},
            preassigned_person_ids=[2],
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=transfers, errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    _assert_solved(result)
    assert set(result.transfer_assignments[41]) == {1, 2}
    assert result.field_assignments[41]["field_driver"] == [1]
    assert result.field_assignments[41]["field_transferees"] == [2]
    assert result.assignments[50] == [2]


def test_no_dynamic_capacity_reports_unreachable_destination_assignment():
    """Without capacity for a dynamic passenger, the destination task is infeasible."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=2, capabilities=[], home_location_id=1, unavailable_intervals=[]),
    ]
    transfers = [
        NormTransfer(
            id=41,
            from_location_id=1,
            to_location_id=2,
            depart_time=540,
            arrive_time=570,
            capacity=1,
            requirements={},
            locked_person_ids=[1],
        )
    ]
    tasks = [
        NormTask(
            id=50,
            name="Venue preparation",
            location_id=2,
            start_time=600,
            end_time=660,
            requirements={},
            preassigned_person_ids=[2],
        )
    ]

    errors = check_flow(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=transfers, errors=[], floating_tasks=[])
    )

    assert errors
    assert any("cannot reach this location" in error for error in errors)


def test_locked_transfer_passenger_must_be_at_origin():
    """A locked transfer passenger cannot be silently dropped when not at the origin."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=2, unavailable_intervals=[]),
    ]
    transfers = [
        NormTransfer(
            id=41,
            from_location_id=1,
            to_location_id=2,
            depart_time=540,
            arrive_time=570,
            capacity=1,
            requirements={},
            locked_person_ids=[1],
        )
    ]

    errors = check_flow(
        NormalizedFlowInput(persons=persons, tasks=[], transfers=transfers, errors=[], floating_tasks=[])
    )

    assert errors
