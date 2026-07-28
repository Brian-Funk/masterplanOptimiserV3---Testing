"""Current persistence contract for task-type working-time policy."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.task import TaskType


def test_current_task_types_default_to_counted_work(tmp_path):
    """The current schema stores an explicit, non-null enabled policy."""

    engine = create_engine(f"sqlite:///{tmp_path / 'current-task-types.db'}")
    TaskType.__table__.create(engine)
    with Session(engine) as session:
        task_type = TaskType(name="Current")
        session.add(task_type)
        session.commit()
        session.refresh(task_type)
        assert task_type.counts_towards_work_time is True

    columns = {column["name"]: column for column in inspect(engine).get_columns("task_types")}
    assert columns["counts_towards_work_time"]["nullable"] is False
