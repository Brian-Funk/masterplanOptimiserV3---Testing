"""
Desktop backend test fixtures.

Overrides the FastAPI app's database to use SQLite in-memory,
provides an authenticated httpx Client with the desktop auth token.
"""
import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker, Session

# ── Add desktop backend + compute/src to sys.path ──
_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
_DESKTOP_BACKEND = (
    _ROOT.parent.parent
    / "MasterplanOptimiserV3 - App"
    / "masterplanOptimiserV3 - App"
    / "backend"
)
_COMPUTE_SRC = (
    _ROOT.parent.parent
    / "MasterplanOptimiserV3 - App"
    / "masterplanOptimiserV3 - App"
    / "compute"
    / "src"
)
for p in (_DESKTOP_BACKEND, _COMPUTE_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Set the desktop auth token BEFORE importing app code
_TEST_TOKEN = "test-desktop-token-for-testing"
os.environ["DESKTOP_AUTH_TOKEN"] = _TEST_TOKEN

from app.db.database import Base, get_db
from app.main import app
from app.models.event import Event
from app.models.location import Location
from app.models.person import Person
from app.models.task import Task, TaskType

from httpx import ASGITransport, Client


# ── Test database engine (SQLite in-memory) ──

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


@sa_event.listens_for(_test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine,
)


@pytest.fixture(autouse=True)
def db() -> Generator[Session, None, None]:
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=_test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def _override_db(db: Session):
    """Override FastAPI's get_db dependency to use the test session."""
    def _get_test_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


# ── Authenticated client ──

@pytest.fixture
def client() -> Client:
    """httpx Client with the desktop auth token header."""
    return Client(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={
            "x-desktop-token": _TEST_TOKEN,
            "Content-Type": "application/json",
        },
    )


@pytest.fixture
def unauth_client() -> Client:
    """httpx Client WITHOUT the desktop auth token (for testing auth)."""
    return Client(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Content-Type": "application/json"},
    )


# ── Factory helpers ──

def create_test_event(db: Session, name: str = "Test Event") -> Event:
    """Insert an event and return it."""
    event = Event(
        name=name,
        location="Test Location",
        start_date="2026-08-01",
        end_date="2026-08-10",
        status="draft",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_test_location(
    db: Session, event_id: int, name: str = "Main Hall",
) -> Location:
    """Insert a location and return it."""
    loc = Location(event_id=event_id, name=name)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def create_test_task_type(
    db: Session, name: str = "Workshop", task_type_id: int | None = None,
) -> TaskType:
    """Insert a task type and return it."""
    tt = TaskType(name=name, is_active=True)
    if task_type_id is not None:
        tt.id = task_type_id
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return tt


def create_test_person(
    db: Session,
    event_id: int,
    first_name: str = "Jane",
    last_name: str = "Doe",
    location_id: int | None = None,
) -> Person:
    """Insert a person and return it."""
    person = Person(
        event_id=event_id,
        first_name=first_name,
        last_name=last_name,
        home_location_id=location_id,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def create_test_task(
    db: Session,
    event_id: int,
    task_type_id: int,
    title: str = "Test Task",
) -> Task:
    """Insert a task and return it."""
    task = Task(
        event_id=event_id,
        task_type_id=task_type_id,
        title=title,
        constraints={},
        optimised={},
        final={},
        additional={},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
