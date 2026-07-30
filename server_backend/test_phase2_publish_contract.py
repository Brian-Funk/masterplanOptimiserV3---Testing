"""Independent contract tests for the Server Phase 2 publish boundary."""

import pytest
from pydantic import ValidationError

from app.api.v1.publish import PublishPayload


def _task(**updates):
    task = {
        "id": 1,
        "name": "Operational task",
        "start": "2026-08-01T09:00:00+00:00",
        "end": "2026-08-01T10:00:00+00:00",
        "attendees": [],
    }
    task.update(updates)
    return task


@pytest.mark.parametrize("contract_version", [None, "unknown", "2026-07-29"])
def test_publish_rejects_missing_or_unknown_contract_version(contract_version):
    payload = {"tasks": [], "persons": []}
    if contract_version is not None:
        payload["contract_version"] = contract_version

    with pytest.raises(ValidationError):
        PublishPayload.model_validate(payload)


def test_publish_rejects_unclassified_field_value():
    with pytest.raises(ValidationError, match="unclassified"):
        PublishPayload.model_validate({
            "contract_version": "2026-07-30",
            "tasks": [_task(field_values={"unknown_notes": "private"})],
            "persons": [],
        })


def test_publish_rejects_retired_theme_compatibility_payload():
    with pytest.raises(ValidationError):
        PublishPayload.model_validate({
            "contract_version": "2026-07-30",
            "tasks": [],
            "persons": [],
            "theme": {"logo_color_1": "#ffffff"},
        })


def test_publish_rejects_never_publish_value_even_when_declared():
    with pytest.raises(ValidationError, match="never_publish"):
        PublishPayload.model_validate({
            "contract_version": "2026-07-30",
            "tasks": [_task(
                field_values={"notes": "private"},
                field_definitions=[{
                    "id": "notes",
                    "name": "Notes",
                    "type": "text",
                    "purpose": "operational_instruction",
                    "visibility": "never_publish",
                }],
            )],
            "persons": [],
        })


def test_publish_accepts_reviewed_bounded_field_without_additional_blob():
    payload = PublishPayload.model_validate({
        "contract_version": "2026-07-30",
        "tasks": [_task(
            field_values={"brief": "Bring the room key"},
            field_definitions=[{
                "id": "brief",
                "name": "Operational brief",
                "type": "text",
                "purpose": "operational_instruction",
                "visibility": "organiser",
            }],
        )],
        "persons": [],
    })

    assert payload.contract_version == "2026-07-30"
    assert not hasattr(payload.tasks[0], "additional")


def test_publish_rejects_person_assignments_in_generic_values():
    with pytest.raises(ValidationError, match="structured assignment contract"):
        PublishPayload.model_validate({
            "contract_version": "2026-07-30",
            "tasks": [_task(
                field_values={"crew": [{"name": "Ada", "person_id": 1}]},
                field_definitions=[{
                    "id": "crew",
                    "name": "Assigned crew",
                    "type": "persons_list",
                    "purpose": "assignment",
                    "visibility": "participant",
                }],
            )],
            "persons": [],
        })
