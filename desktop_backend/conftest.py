"""
Desktop backend test fixtures.

Overrides the FastAPI app's database to use SQLite in-memory,
provides an authenticated FastAPI TestClient with the desktop auth token.
"""
import os
import sys
from datetime import date
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sa_event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

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


class FakeSecureCredentialStore:
    """In-memory secure credential store used by desktop backend tests."""

    def __init__(self):
        self.values: dict[str, str] = {}
        self.is_available = True

    def available(self) -> bool:
        return self.is_available

    def get(self, account: str) -> str | None:
        if not self.is_available:
            from app.core.secure_credentials import SecureCredentialStoreUnavailable

            raise SecureCredentialStoreUnavailable("OS credential storage is not available.")
        return self.values.get(account)

    def set(self, account: str, value: str) -> None:
        if not self.is_available:
            from app.core.secure_credentials import SecureCredentialStoreUnavailable

            raise SecureCredentialStoreUnavailable("OS credential storage is not available.")
        if not isinstance(value, str):
            raise TypeError("Secure credential values must be strings.")
        self.values[account] = value

    def delete(self, account: str) -> None:
        if not self.is_available:
            from app.core.secure_credentials import SecureCredentialStoreUnavailable

            raise SecureCredentialStoreUnavailable("OS credential storage is not available.")
        self.values.pop(account, None)


@pytest.fixture(autouse=True)
def secure_credential_store():
    """Use a fake secure store for all desktop backend tests."""
    from app.core.secure_credentials import set_credential_store_for_tests

    store = FakeSecureCredentialStore()
    set_credential_store_for_tests(store)
    try:
        yield store
    finally:
        set_credential_store_for_tests(None)

 


# ── Test database engine (SQLite in-memory) ──

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@sa_event.listens_for(_test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine,
)


def _create_legacy_tables() -> None:
    """Create legacy tables still referenced by cleanup SQL but not mapped."""
    with _test_engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS task_descriptions "
            "(id INTEGER PRIMARY KEY, event_id INTEGER, task_id INTEGER, content TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS attachments "
            "(id INTEGER PRIMARY KEY, event_id INTEGER, filename TEXT)"
        ))


def _drop_legacy_tables() -> None:
    with _test_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS attachments"))
        conn.execute(text("DROP TABLE IF EXISTS task_descriptions"))


@pytest.fixture(autouse=True)
def db() -> Generator[Session, None, None]:
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=_test_engine)
    _create_legacy_tables()
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        _drop_legacy_tables()
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
def client() -> Generator[TestClient, None, None]:
    """TestClient with the desktop auth token header."""
    with TestClient(
        app,
        base_url="http://localhost",
        headers={
            "x-desktop-token": _TEST_TOKEN,
            "Content-Type": "application/json",
        },
    ) as test_client:
        yield test_client


@pytest.fixture
def unauth_client() -> Generator[TestClient, None, None]:
    """TestClient WITHOUT the desktop auth token for testing auth."""
    with TestClient(
        app,
        base_url="http://localhost",
        headers={"Content-Type": "application/json"},
    ) as test_client:
        yield test_client


# ── Factory helpers ──

def create_test_event(db: Session, name: str = "Test Event") -> Event:
    """Insert an event and return it."""
    event = Event(
        name=name,
        location="Test Location",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 10),
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
