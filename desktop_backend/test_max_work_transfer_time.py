"""Regression tests for max working-hours accounting across transfers."""

from fatigue_optimizer import OptimizationConfig, optimize_with_fatigue
from flow_checker import (
    NormPerson,
    NormTask,
    NormTransfer,
    NormalizedFlowInput,
    check_flow,
)


def _fast_config():
    return OptimizationConfig(
        scale=100,
        break_threshold_min=30,
        break_effect=-3.0,
        max_time_seconds=10.0,
    )


def _input_with_transfer_and_task(max_minutes: int) -> NormalizedFlowInput:
    return NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=[],
                max_work_minutes_per_day=max_minutes,
                unavailable_intervals=[],
            )
        ],
        tasks=[
            NormTask(
                id=101,
                name="Destination shift",
                location_id=2,
                start_time=600,
                end_time=720,
                requirements={},
                preassigned_person_ids=[1],
            )
        ],
        transfers=[
            NormTransfer(
                id=201,
                from_location_id=1,
                to_location_id=2,
                depart_time=540,
                arrive_time=600,
                capacity=1,
                requirements={},
                locked_person_ids=[1],
                person_field_assignments={"driver": [1]},
            )
        ],
        floating_tasks=[],
        errors=[],
    )


def test_optimizer_counts_transfer_time_against_max_work_limit():
    """Transfer time plus task time must fit inside the hard max-hours limit."""
    result = optimize_with_fatigue(_input_with_transfer_and_task(150), _fast_config())

    assert result.status == "INFEASIBLE"


def test_flow_checker_counts_transfer_time_against_max_work_limit():
    """Flow check uses the same active-time accounting as optimisation."""
    errors = check_flow(_input_with_transfer_and_task(150))

    assert errors


def test_max_work_limit_allows_schedule_exactly_at_limit():
    """A person can work exactly up to their limit including transfer time."""
    optimiser_result = optimize_with_fatigue(
        _input_with_transfer_and_task(180),
        _fast_config(),
    )
    flow_errors = check_flow(_input_with_transfer_and_task(180))

    assert optimiser_result.status in {"OPTIMAL", "FEASIBLE"}
    assert optimiser_result.transfer_assignments == {201: [1]}
    assert optimiser_result.assignments == {101: [1]}
    assert flow_errors == []


def test_transfer_only_time_counts_against_max_work_limit():
    """A locked transfer passenger is active even without a destination task."""
    input_data = _input_with_transfer_and_task(30)
    input_data.tasks = []

    result = optimize_with_fatigue(input_data, _fast_config())
    errors = check_flow(input_data)

    assert result.status == "INFEASIBLE"
    assert errors


def _single_direct_task_input(max_minutes: int) -> NormalizedFlowInput:
    return NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=[],
                max_work_minutes_per_day=max_minutes,
                unavailable_intervals=[],
            )
        ],
        tasks=[
            NormTask(
                id=301,
                name="Long direct shift",
                location_id=1,
                start_time=480,
                end_time=600,
                requirements={},
                preassigned_person_ids=[1],
            )
        ],
        transfers=[],
        floating_tasks=[],
        errors=[],
    )


def _single_capability_task_input(max_minutes: int) -> NormalizedFlowInput:
    return NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=["setup"],
                max_work_minutes_per_day=max_minutes,
                unavailable_intervals=[],
            )
        ],
        tasks=[
            NormTask(
                id=302,
                name="Long capability shift",
                location_id=1,
                start_time=480,
                end_time=600,
                requirements={"setup": 1},
                preassigned_person_ids=[],
            )
        ],
        transfers=[],
        floating_tasks=[],
        errors=[],
    )


def test_optimizer_and_flow_checker_reject_direct_task_over_max_work_limit():
    input_data = _single_direct_task_input(60)

    result = optimize_with_fatigue(input_data, _fast_config())
    errors = check_flow(input_data)

    assert result.status == "INFEASIBLE"
    assert errors


def test_optimizer_and_flow_checker_reject_capability_work_over_max_work_limit():
    input_data = _single_capability_task_input(60)

    result = optimize_with_fatigue(input_data, _fast_config())
    errors = check_flow(input_data)

    assert result.status == "INFEASIBLE"
    assert errors
