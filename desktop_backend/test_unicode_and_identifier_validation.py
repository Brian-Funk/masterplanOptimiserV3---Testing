"""Tests for Unicode display names and ASCII-only technical identifiers."""

import sys

from flow_checker import (
    NormFloatingTask,
    NormPerson,
    NormalizedFlowInput,
    check_flow,
)


class StrictCharmapStdout:
    """Test stream that behaves like a legacy Windows charmap console."""

    encoding = "cp1252"

    def __init__(self):
        self.output = []

    def write(self, text):
        """Write text only when it can be encoded by the configured charmap."""
        text.encode(self.encoding)
        self.output.append(text)
        return len(text)

    def flush(self):
        """Match the file-like API expected by print."""
        return None


def test_flow_checker_allows_unicode_task_names_with_legacy_console(monkeypatch):
    """Unicode task names must not crash flow-check diagnostic output."""
    stream = StrictCharmapStdout()
    monkeypatch.setenv("DEBUG_OPTIMIZER_LOGS", "true")
    monkeypatch.setattr(sys, "stdout", stream)

    normalized = NormalizedFlowInput(
        persons=[
            NormPerson(
                id=1,
                home_location_id=1,
                capabilities=["is_orga"],
                max_work_minutes_per_day=480,
                unavailable_intervals=[],
            )
        ],
        tasks=[],
        transfers=[],
        errors=[],
        floating_tasks=[
            NormFloatingTask(
                id=100,
                name="Zaświadczać",
                location_id=1,
                window_start_time=480,
                window_end_time=540,
                duration=60,
                requirements={"is_orga": 1},
                preassigned_person_ids=[],
            )
        ],
    )

    result = check_flow(normalized, max_time_seconds=5.0)

    assert result == []
    assert "\\u0107" in "".join(stream.output)


def test_capability_machine_name_rejects_unicode_but_display_name_is_allowed(client):
    """Capability display names may be Unicode, but machine names stay ASCII."""
    cap_type = client.post(
        "/api/v1/capability-types/",
        json={"name": "Roles", "sort_order": 0},
    )
    assert cap_type.status_code == 201
    cap_type_id = cap_type.json()["id"]

    invalid = client.post(
        "/api/v1/capabilities",
        json={
            "machine_name": "ćapability",
            "name": "Ćapability",
            "capability_type_id": cap_type_id,
        },
    )
    assert invalid.status_code == 400
    assert "ASCII" in invalid.json()["detail"]

    valid = client.post(
        "/api/v1/capabilities",
        json={
            "machine_name": "valid_capability",
            "name": "Zaświadczać",
            "capability_type_id": cap_type_id,
        },
    )
    assert valid.status_code == 201
    assert valid.json()["machine_name"] == "valid_capability"
    assert valid.json()["name"] == "Zaświadczać"


def test_task_template_machine_name_rejects_unicode_but_display_name_is_allowed(client):
    """Task template display names may be Unicode, but machine names stay ASCII."""
    task_type = client.post(
        "/api/v1/task-types/",
        json={"name": "Session", "sort_order": 0},
    )
    assert task_type.status_code == 201
    task_type_id = task_type.json()["id"]

    invalid = client.post(
        "/api/v1/task-templates/",
        json={
            "machine_name": "demo_ć",
            "name": "Demo ć",
            "task_type_id": task_type_id,
            "fields": [],
            "is_floating": False,
            "is_transfer": False,
        },
    )
    assert invalid.status_code == 400
    assert "ASCII" in invalid.json()["detail"]

    valid = client.post(
        "/api/v1/task-templates/",
        json={
            "machine_name": "demo_template",
            "name": "Zaświadczać template",
            "task_type_id": task_type_id,
            "fields": [],
            "is_floating": False,
            "is_transfer": False,
        },
    )
    assert valid.status_code == 201
    assert valid.json()["machine_name"] == "demo_template"
    assert valid.json()["name"] == "Zaświadczać template"
