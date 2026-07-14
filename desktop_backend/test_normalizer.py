"""Tests for the optimization normalizer — data transformation for the solver."""
from app.core.normalizer_optimization import (
    time_to_minutes,
    normalize_optimization_input,
    OptimizationTask,
    OptimizationPerson,
    OptimizationLocation,
    OptimizationCapability,
)
from app.core.normalizer import (
    normalize_flow_input,
    Task as FlowTask,
    Person as FlowPerson,
    Location as FlowLocation,
    Capability as FlowCapability,
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


def test_flow_person_name_metadata_survives_legacy_solver_class(monkeypatch):
    """Hot reloads can attach names to a previously loaded NormPerson class."""
    import app.core.normalizer as flow_normalizer

    class LegacyNormPerson:
        def __init__(
            self,
            id,
            home_location_id,
            capabilities,
            max_work_minutes_per_day=None,
            unavailable_intervals=None,
            initial_fatigue=0.0,
        ):
            self.id = id
            self.home_location_id = home_location_id
            self.capabilities = capabilities
            self.max_work_minutes_per_day = max_work_minutes_per_day
            self.unavailable_intervals = unavailable_intervals or []
            self.initial_fatigue = initial_fatigue

    monkeypatch.setattr(flow_normalizer, "NormPerson", LegacyNormPerson)
    result = flow_normalizer.normalize_flow_input(
        tasks=[],
        persons=[
            FlowPerson(
                id=9,
                first_name="Alex",
                last_name="Example",
                home_location_id=1,
            )
        ],
        locations=[],
        capabilities=[],
    )

    assert result.persons[0].name == "Alex Example"


def test_normalize_person_unavailability():
    """Person with unavailability intervals in global_data."""
    persons = [
        OptimizationPerson(
            id=1,
            first_name="C",
            last_name="D",
            global_data={
                "unavailabilities": [
                    {"from": "2026-06-10T08:00", "to": "2026-06-10T09:00"},
                ],
            },
        ),
    ]
    result = normalize_optimization_input(
        tasks=[], persons=persons, locations=[],
        capabilities=[], task_type_fatigue_map={},
        working_day_date="2026-06-10",
    )
    assert result.persons[0].unavailable_intervals == [(480, 540)]


def test_flow_and_optimization_normalizers_scope_dated_unavailability_to_selected_day():
    global_data = {
        "unavailabilities": [
            {"from": "2026-06-10T18:00", "to": "2026-06-10T20:00"},
        ],
    }

    optimisation = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Ben",
                last_name="Evening",
                global_data=global_data,
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-11",
    )
    flow = normalize_flow_input(
        tasks=[],
        persons=[
            FlowPerson(
                id=1,
                first_name="Ben",
                last_name="Evening",
                global_data=global_data,
            )
        ],
        locations=[],
        capabilities=[],
        working_day_date="2026-06-11",
    )

    assert optimisation.persons[0].unavailable_intervals == []
    assert flow.persons[0].unavailable_intervals == []


def test_flow_and_optimization_normalizers_apply_dated_unavailability_on_matching_day():
    global_data = {
        "unavailabilities": [
            {"from": "2026-06-10T18:00", "to": "2026-06-10T20:00"},
        ],
    }

    optimisation = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Katya",
                last_name="Unavailable",
                global_data=global_data,
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
    )
    flow = normalize_flow_input(
        tasks=[],
        persons=[
            FlowPerson(
                id=1,
                first_name="Katya",
                last_name="Unavailable",
                global_data=global_data,
            )
        ],
        locations=[],
        capabilities=[],
        working_day_date="2026-06-10",
    )

    assert optimisation.persons[0].unavailable_intervals == [(1080, 1200)]
    assert flow.persons[0].unavailable_intervals == [(1080, 1200)]


def test_unavailability_respects_working_day_boundary_tail():
    global_data = {
        "unavailabilities": [
            {"from": "2026-06-11T01:00", "to": "2026-06-11T02:00"},
        ],
    }

    result = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Night",
                last_name="Tail",
                global_data=global_data,
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
        working_day_boundary_offset_hour=4,
    )

    assert result.persons[0].unavailable_intervals == [(1500, 1560)]


def test_overnight_unavailability_is_continuous_for_working_day():
    result = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Over",
                last_name="Night",
                global_data={
                    "unavailabilities": [
                        {"from": "2026-06-10T22:00", "to": "2026-06-11T02:00"},
                    ],
                },
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
        working_day_boundary_offset_hour=4,
    )

    assert result.persons[0].unavailable_intervals == [(1320, 1560)]


def test_legacy_unavailable_intervals_and_time_only_entries_still_work():
    result = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Legacy",
                last_name="Intervals",
                global_data={
                    "unavailable_intervals": [{"start": 480, "end": 540}],
                    "unavailabilities": [{"start": "18:00", "end": "20:00"}],
                },
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
    )

    assert result.persons[0].unavailable_intervals == [(480, 540), (1080, 1200)]


def test_invalid_unavailability_is_reported_without_crashing():
    result = normalize_optimization_input(
        tasks=[],
        persons=[
            OptimizationPerson(
                id=1,
                first_name="Invalid",
                last_name="Entry",
                global_data={"unavailabilities": [{"from": "", "to": "not-time"}]},
            )
        ],
        locations=[],
        capabilities=[],
        task_type_fatigue_map={},
        working_day_date="2026-06-10",
    )

    assert result.persons[0].unavailable_intervals == []
    assert result.errors == ["Person 1: Ignored invalid unavailability entry."]


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
