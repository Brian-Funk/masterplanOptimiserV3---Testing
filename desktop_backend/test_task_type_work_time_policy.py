"""Persistence compatibility tests for task-type working-time policy."""

from sqlalchemy import create_engine, text

from app.main import _run_schema_migrations


def test_legacy_task_types_are_migrated_to_counted_work(tmp_path):
    """Existing task types receive a non-null, enabled policy by default."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-task-types.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE task_types "
                "(id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO task_types (id, name) VALUES (1, 'Existing')")
        )

    _run_schema_migrations(engine)

    with engine.connect() as connection:
        value = connection.execute(
            text(
                "SELECT counts_towards_work_time FROM task_types WHERE id = 1"
            )
        ).scalar_one()
        columns = {
            row[1]: row
            for row in connection.execute(text("PRAGMA table_info(task_types)"))
        }

    assert value == 1
    assert columns["counts_towards_work_time"][3] == 1
    assert columns["counts_towards_work_time"][4] == "1"
