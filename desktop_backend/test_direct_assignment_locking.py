"""Regression tests for exact direct person assignments in optimisation."""

from app.core.normalizer_optimization import (
    OptimizationLocation,
    OptimizationPerson,
    OptimizationTask,
    normalize_optimization_input,
)
from app.models.task_template import TaskTemplate
from desktop_backend.conftest import create_test_task_type
from fatigue_optimizer import OptimizationConfig, optimize_with_fatigue
from flow_checker import (
    NormFloatingTask,
    NormPerson,
    NormTask,
    NormalizedFlowInput,
    check_flow,
)


def _fast_config():
    """Return a deterministic low-timeout optimiser config for regressions."""
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


def test_normalizer_extracts_persons_list_values_as_preassigned_person_ids(db):
    """A template persons_list field becomes direct preassigned person ids."""
    create_test_task_type(db, name="Direct assignment", task_type_id=1)

    template = TaskTemplate(
        machine_name="direct_assignment_template",
        name="Direct Assignment Template",
        task_type_id=1,
        fields=[
            {
                "id": "direct_people",
                "name": "Direct people",
                "type": "persons_list",
                "category": "conditions",
            }
        ],
        is_floating=False,
        is_transfer=False,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    result = normalize_optimization_input(
        tasks=[
            OptimizationTask(
                id=100,
                name="Core-Debrief",
                task_type_id=1,
                template_id=template.id,
                location_id=1,
                start_time=480,
                end_time=540,
                field_values={"direct_people": [6, 2, 999, 4]},
            )
        ],
        persons=[
            OptimizationPerson(id=2, first_name="Person", last_name="Two", home_location_id=1),
            OptimizationPerson(id=4, first_name="Person", last_name="Four", home_location_id=1),
            OptimizationPerson(id=6, first_name="Person", last_name="Six", home_location_id=1),
        ],
        locations=[OptimizationLocation(id=1, name="Room A")],
        capabilities=[],
        task_type_fatigue_map={1: 1.0},
        db=db,
    )

    assert result.errors == []
    assert result.tasks[0].preassigned_person_ids == [6, 2, 4]


def test_optimiser_direct_assignment_single_person_exact_without_capabilities():
    """A direct-only task must keep exactly the selected person."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=2, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=3, capabilities=[], home_location_id=1, unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=100,
            name="Direct only",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=[2],
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    _assert_solved(result)
    assert result.assignments[100] == [2]


def test_optimiser_direct_assignment_multiple_people_exact_without_capabilities():
    """A direct-only task with multiple selected people must not gain extras."""
    persons = [
        NormPerson(id=pid, capabilities=[], home_location_id=1, unavailable_intervals=[])
        for pid in range(1, 7)
    ]
    tasks = [
        NormTask(
            id=101,
            name="Direct group",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=[1, 3, 5],
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    _assert_solved(result)
    assert set(result.assignments[101]) == {1, 3, 5}


def test_optimiser_logged_case_does_not_add_idle_people_to_direct_only_task():
    """The logged Core-Debrief case must not acquire unrelated idle people."""
    direct_people = [6, 2, 4, 5, 7, 3, 1]
    all_people = direct_people + [8, 9, 10, 11]
    persons = [
        NormPerson(id=pid, capabilities=[], home_location_id=1, unavailable_intervals=[])
        for pid in all_people
    ]
    tasks = [
        NormTask(
            id=102,
            name="Core-Debrief",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=direct_people,
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    _assert_solved(result)
    assert set(result.assignments[102]) == set(direct_people)
    assert not (set(result.assignments[102]) & {8, 9, 10, 11})


def test_optimiser_direct_assignment_with_capability_keeps_provider_separate():
    """Capability providers can be chosen without polluting direct assignments."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=2, capabilities=["is_driver"], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=3, capabilities=["is_driver"], home_location_id=1, unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=103,
            name="Direct plus driver",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={"is_driver": 1},
            preassigned_person_ids=[1],
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    _assert_solved(result)
    assert result.assignments[103] == [1]
    assert (103, "is_driver") in result.capability_assignments
    assert set(result.capability_assignments[(103, "is_driver")]).issubset({2, 3})


def test_optimiser_floating_direct_assignment_multiple_people_exact():
    """A floating direct-only task must keep exactly the selected people."""
    persons = [
        NormPerson(id=pid, capabilities=[], home_location_id=1, unavailable_intervals=[])
        for pid in range(1, 5)
    ]
    floating_tasks = [
        NormFloatingTask(
            id=200,
            name="Floating direct group",
            location_id=1,
            window_start_time=480,
            window_end_time=600,
            duration=60,
            requirements={},
            preassigned_person_ids=[1, 2],
        )
    ]
    floating_tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=[], transfers=[], errors=[], floating_tasks=floating_tasks),
        config=_fast_config(),
    )

    _assert_solved(result)
    chosen_assignments = [
        assigned
        for task_id, assigned in result.assignments.items()
        if str(task_id).startswith("200_cand_")
    ]
    assert len(chosen_assignments) == 1
    assert set(chosen_assignments[0]) == {1, 2}


def test_optimiser_directly_assigned_unavailable_person_is_infeasible():
    """A locked direct person must not be silently replaced when unavailable."""
    persons = [
        NormPerson(
            id=1,
            capabilities=[],
            home_location_id=1,
            unavailable_intervals=[(480, 540)],
        ),
        NormPerson(id=2, capabilities=[], home_location_id=1, unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=104,
            name="Unavailable direct",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=[1],
        )
    ]
    tasks[0].fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    assert result.status == "INFEASIBLE"


def test_flow_checker_accepts_multiple_direct_assignments_with_idle_people():
    """Flow checker accepts direct-only tasks without needing idle extras."""
    direct_people = [6, 2, 4, 5, 7, 3, 1]
    persons = [
        NormPerson(id=pid, home_location_id=1, capabilities=[], unavailable_intervals=[])
        for pid in direct_people + [9, 10]
    ]
    tasks = [
        NormTask(
            id=300,
            name="Core-Debrief",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=direct_people,
        )
    ]

    result = check_flow(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[])
    )

    assert result == []


def test_flow_checker_direct_person_unavailability_is_not_replaced():
    """Flow checker rejects locked direct people who cannot do the task."""
    persons = [
        NormPerson(
            id=1,
            home_location_id=1,
            capabilities=[],
            unavailable_intervals=[(480, 540)],
        ),
        NormPerson(id=2, home_location_id=1, capabilities=[], unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=301,
            name="Unavailable Direct",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=[1],
        )
    ]

    result = check_flow(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[])
    )

    assert result


def test_optimiser_directly_assigned_unreachable_location_is_infeasible_without_transfer():
    """A locked direct person must not teleport to an unreachable task location."""
    persons = [
        NormPerson(id=1, capabilities=[], home_location_id=1, unavailable_intervals=[]),
        NormPerson(id=2, capabilities=["setup"], home_location_id=1, unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=105,
            name="Anchor task",
            location_id=1,
            start_time=480,
            end_time=510,
            requirements={"setup": 1},
            preassigned_person_ids=[],
        ),
        NormTask(
            id=106,
            name="Unreachable direct",
            location_id=2,
            start_time=540,
            end_time=600,
            requirements={},
            preassigned_person_ids=[1],
        ),
    ]
    for task in tasks:
        task.fatigue_per_minute = 1.0

    result = optimize_with_fatigue(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[]),
        config=_fast_config(),
    )

    assert result.status == "INFEASIBLE"


def test_flow_checker_accepts_floating_multiple_direct_assignments():
    """Flow checker accepts floating direct tasks with multiple selected people."""
    persons = [
        NormPerson(id=pid, home_location_id=1, capabilities=[], unavailable_intervals=[])
        for pid in [1, 2, 3]
    ]
    floating_tasks = [
        NormFloatingTask(
            id=400,
            name="Floating Direct",
            location_id=1,
            window_start_time=480,
            window_end_time=600,
            duration=60,
            requirements={},
            preassigned_person_ids=[1, 2],
        )
    ]

    result = check_flow(
        NormalizedFlowInput(persons=persons, tasks=[], transfers=[], errors=[], floating_tasks=floating_tasks)
    )

    assert result == []


def test_flow_checker_locked_people_cannot_cover_overlapping_capability_task():
    """People locked to a direct task cannot also cover an overlapping task."""
    persons = [
        NormPerson(id=1, home_location_id=1, capabilities=["cap_a"], unavailable_intervals=[]),
        NormPerson(id=2, home_location_id=1, capabilities=["cap_a"], unavailable_intervals=[]),
    ]
    tasks = [
        NormTask(
            id=500,
            name="Locked group",
            location_id=1,
            start_time=480,
            end_time=540,
            requirements={},
            preassigned_person_ids=[1, 2],
        ),
        NormTask(
            id=501,
            name="Overlapping capability task",
            location_id=1,
            start_time=500,
            end_time=560,
            requirements={"cap_a": 1},
            preassigned_person_ids=[],
        ),
    ]

    result = check_flow(
        NormalizedFlowInput(persons=persons, tasks=tasks, transfers=[], errors=[], floating_tasks=[])
    )

    assert result
