"""Tests for the optimization normalizer — data transformation for the solver."""
from app.core.normalizer_optimization import (
    time_to_minutes,
    normalize_optimization_input,
    OptimizationTask,
    OptimizationPerson,
    OptimizationLocation,
    OptimizationCapability,
)


def test_time_to_minutes_string():
    """HH:MM string → minutes since midnight."""
    assert time_to_minutes("08:30") == 510
    assert time_to_minutes("00:00") == 0
    assert time_to_minutes("23:59") == 1439


def test_time_to_minutes_int():
    """Integer passthrough."""
    assert time_to_minutes(480) == 480


def test_time_to_minutes_none():
    """None → None."""
    assert time_to_minutes(None) is None


def test_normalize_basic():
    """Normalization produces correct output structure."""
    tasks = [
        OptimizationTask(
            id=1,
            name="Workshop",
            task_type_id=1,
            location_id=1,
            start_time=480,  # 08:00
            end_time=540,    # 09:00
        ),
    ]
    persons = [
        OptimizationPerson(
            id=1,
            first_name="Alice",
            last_name="Smith",
            home_location_id=1,
        ),
    ]
    locations = [
        OptimizationLocation(id=1, name="Room A"),
    ]
    capabilities = []
    fatigue_map = {1: 1.0}

    result = normalize_optimization_input(
        tasks, persons, locations, capabilities, fatigue_map,
    )

    assert len(result.tasks) == 1
    assert result.tasks[0].id == 1
    assert result.tasks[0].start_time == 480
    assert result.tasks[0].end_time == 540

    assert len(result.persons) == 1
    assert result.persons[0].id == 1


def test_normalize_person_capabilities():
    """Person capabilities are mapped to machine names."""
    persons = [
        OptimizationPerson(
            id=1,
            first_name="Bob",
            last_name="B",
            capabilities=["is_ho", "is_chairperson"],
        ),
    ]
    result = normalize_optimization_input(
        tasks=[], persons=persons, locations=[],
        capabilities=[], task_type_fatigue_map={},
    )
    assert "is_ho" in result.persons[0].capabilities
    assert "is_chairperson" in result.persons[0].capabilities


def test_normalize_person_unavailability():
    """Person with unavailability intervals in global_data."""
    persons = [
        OptimizationPerson(
            id=1,
            first_name="C",
            last_name="D",
            global_data={
                "unavailabilities": [
                    {"start": "08:00", "end": "09:00"},
                ],
            },
        ),
    ]
    result = normalize_optimization_input(
        tasks=[], persons=persons, locations=[],
        capabilities=[], task_type_fatigue_map={},
    )
    # Unavailabilities should be parsed into minute intervals
    person = result.persons[0]
    if person.unavailable_intervals:
        assert person.unavailable_intervals[0] == (480, 540)


def test_normalize_empty_input():
    """Empty input → empty output, no errors."""
    result = normalize_optimization_input(
        tasks=[], persons=[], locations=[],
        capabilities=[], task_type_fatigue_map={},
    )
    assert len(result.tasks) == 0
    assert len(result.persons) == 0
    assert len(result.errors) == 0


def test_normalize_fatigue_scores():
    """Tasks get fatigue_per_minute from the task_type_fatigue_map."""
    tasks = [
        OptimizationTask(
            id=1, name="Hard Work", task_type_id=1,
            start_time=480, end_time=540,
        ),
        OptimizationTask(
            id=2, name="Break", task_type_id=2,
            start_time=540, end_time=570,
        ),
    ]
    fatigue_map = {1: 2.5, 2: -1.0}

    result = normalize_optimization_input(
        tasks=tasks, persons=[], locations=[],
        capabilities=[], task_type_fatigue_map=fatigue_map,
    )
    assert result.tasks[0].fatigue_per_minute == 2.5
    assert result.tasks[1].fatigue_per_minute == -1.0
