"""Regression tests for event deletion cleaning task data."""

import pytest
from sqlalchemy import inspect, text

from app.models.task import Task
from app.models.task_instance import TaskInstance
from app.models.task_template import TaskTemplate
from desktop_backend.conftest import (
    create_test_event,
    create_test_location,
    create_test_person,
    create_test_task_type,
)


def _create_template_with_task_data(db, event_id: int):
    """Create a global type/template plus event task and task instance references."""
    task_type = create_test_task_type(db, name="Cleanup Task Type")
    template = TaskTemplate(
        machine_name="cleanup_template",
        name="Cleanup Template",
        task_type_id=task_type.id,
        fields=[],
        is_floating=False,
        is_transfer=False,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    task = Task(
        event_id=event_id,
        task_template_id=template.id,
        task_type_id=task_type.id,
        title="Legacy task",
        constraints={},
        optimised={},
        final={},
        additional={},
    )
    instance = TaskInstance(
        event_id=event_id,
        template_id=template.id,
        task_type_id=task_type.id,
        name="Draft task instance",
        date="2026-08-01",
        day_index=0,
        field_values={},
    )
    db.add_all([task, instance])
    db.commit()

    return task_type.id, template.id


def _insert_if_table_exists(db, table_names: set[str], table_name: str, statement: str, params: dict) -> None:
    """Insert optional table rows only when the local test schema contains the table."""
    if table_name in table_names:
        db.execute(text(statement), params)


def _create_extra_event_owned_rows(db, event_id: int, template_id: int) -> None:
    """Create non-task event-owned rows that must also be removed before deleting an event."""
    table_names = set(inspect(db.get_bind()).get_table_names())
    location = create_test_location(db, event_id, name="Cleanup Room")
    person = create_test_person(db, event_id, first_name="Cleanup", last_name="User", location_id=location.id)

    _insert_if_table_exists(
        db,
        table_names,
        "description_templates",
        "INSERT INTO description_templates (task_template_id, event_id, fields) "
        "VALUES (:template_id, :event_id, '{}')",
        {"template_id": template_id, "event_id": event_id},
    )
    _insert_if_table_exists(
        db,
        table_names,
        "room_allocations",
        "INSERT INTO room_allocations (event_id, location_id, room_name, assignees) "
        "VALUES (:event_id, :location_id, 'Cleanup Room', '[]')",
        {"event_id": event_id, "location_id": location.id},
    )
    _insert_if_table_exists(
        db,
        table_names,
        "user_persons",
        "INSERT INTO user_persons (person_id, user_id) VALUES (:person_id, NULL)",
        {"person_id": person.id},
    )
    _insert_if_table_exists(
        db,
        table_names,
        "users",
        "INSERT INTO users (event_id, username, email, password_hash, is_root_admin, is_active, is_activated, auth_method) "
        "VALUES (:event_id, 'cleanup-user', 'cleanup@example.test', 'x', 0, 1, 0, 'password')",
        {"event_id": event_id},
    )
    db.commit()


@pytest.mark.parametrize("delete_path", ["/api/v1/events/{event_id}", "/api/v1/data/event/{event_id}"])
def test_delete_event_removes_tasks_and_instances_so_template_can_be_deleted(db, client, delete_path):
    """Deleting an event clears task references that would block template deletion."""
    event = create_test_event(db, name="Imported test event")
    event_id = event.id
    task_type_id, template_id = _create_template_with_task_data(db, event_id)
    _create_extra_event_owned_rows(db, event_id, template_id)

    response = client.delete(delete_path.format(event_id=event_id))

    assert response.status_code == 200
    assert db.query(Task).filter(Task.event_id == event_id).count() == 0
    assert db.query(TaskInstance).filter(TaskInstance.event_id == event_id).count() == 0

    blocked = client.delete(f"/api/v1/task-types/{task_type_id}")
    assert blocked.status_code == 400
    assert "template" in blocked.json()["detail"]

    template_delete = client.delete(f"/api/v1/task-templates/{template_id}")
    assert template_delete.status_code == 204

    task_type_delete = client.delete(f"/api/v1/task-types/{task_type_id}")
    assert task_type_delete.status_code == 204


def test_delete_event_removes_stale_task_instances_that_block_template_deletion(db, client):
    """A stale task instance alone must not survive event deletion."""
    event = create_test_event(db, name="Draft-only event")
    task_type = create_test_task_type(db, name="Draft Task Type")
    template = TaskTemplate(
        machine_name="draft_cleanup_template",
        name="Draft Cleanup Template",
        task_type_id=task_type.id,
        fields=[],
        is_floating=False,
        is_transfer=False,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    instance = TaskInstance(
        event_id=event.id,
        template_id=template.id,
        task_type_id=task_type.id,
        name="Only draft task instance",
        date="2026-08-01",
        day_index=0,
        field_values={},
    )
    db.add(instance)
    db.commit()

    response = client.delete(f"/api/v1/events/{event.id}")

    assert response.status_code == 200
    assert db.query(TaskInstance).filter(TaskInstance.template_id == template.id).count() == 0
    assert client.delete(f"/api/v1/task-templates/{template.id}").status_code == 204
