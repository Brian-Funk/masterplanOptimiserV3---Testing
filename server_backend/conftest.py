"""
Server backend test fixtures.

Overrides the FastAPI app's database to use SQLite in-memory,
provides pre-authenticated TestClient fixtures for each role.
"""
import hashlib
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker, Session

# ── Add server backend to sys.path ──
_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
_SERVER_BACKEND = (
    _ROOT.parent.parent
    / "MasterplanOptimiserV3 - Server"
    / "MasterplanOptimiserV3---Server"
    / "backend"
)
if str(_SERVER_BACKEND) not in sys.path:
    sys.path.insert(0, str(_SERVER_BACKEND))

# Now we can import from the server app
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User, AuthSession, ActivationLink
from app.models.event import Event
from app.models.published import PublishedTask, PublishedPerson, PublishSnapshot, TaskEdit
from app.models.notification import PushSubscription, Announcement, ScheduleChange
from app.models.audit import AuditLog
from app.models.server_setting import ServerSetting
from app.core.sessions import _hash_token

from httpx import ASGITransport, AsyncClient


# ── Test database engine (SQLite in-memory) ──

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

# Enable foreign keys in SQLite
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
    """Create all tables before each test, drop after. Yields a DB session."""
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


# ── Factory helpers ──

def create_test_event(
    db: Session,
    name: str = "Test Event",
    publish_secret: str | None = None,
) -> tuple[Event, str]:
    """Create an event and return (event, raw_publish_secret)."""
    raw_secret = publish_secret or secrets.token_urlsafe(48)
    secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
    event = Event(
        name=name,
        status="draft",
        publish_secret_hash=secret_hash,
        secret_created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event, raw_secret


def create_test_user(
    db: Session,
    username: str = "testuser",
    display_name: str = "Test User",
    event_id: int | None = None,
    is_root_admin: bool = False,
    is_admin: bool = False,
    is_issuer: bool = False,
    can_edit: bool = False,
    is_activated: bool = True,
) -> User:
    """Create a user in the test DB."""
    user = User(
        username=username,
        display_name=display_name,
        email=f"{username}@test.com",
        event_id=event_id,
        is_root_admin=is_root_admin,
        is_admin=is_admin,
        is_issuer=is_issuer,
        can_edit=can_edit,
        is_active=True,
        is_activated=is_activated,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def inject_session(
    db: Session,
    user: User,
    reauth: bool = False,
) -> tuple[str, str]:
    """Create an AuthSession for user. Returns (raw_session_token, csrf_token).

    The raw token is what goes into the session cookie.
    The csrf_token goes into both the csrf cookie and X-CSRF-Token header.
    """
    raw_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    session = AuthSession(
        user_id=user.id,
        session_token=_hash_token(raw_token),
        csrf_token=csrf_token,
        expires_at=now + timedelta(hours=8),
        last_seen_at=now,
        reauth_at=now if reauth else None,
    )
    db.add(session)
    db.commit()
    return raw_token, csrf_token


# ── Pre-authenticated httpx clients ──

from httpx import Client

def _make_client(
    db: Session,
    user: User,
    reauth: bool = False,
) -> Client:
    """Build an httpx Client with session + CSRF cookies/headers set."""
    raw_token, csrf_token = inject_session(db, user, reauth=reauth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    client = Client(
        transport=transport,
        base_url="https://localhost",
        cookies={
            "session_id": raw_token,
            "csrf_token": csrf_token,
        },
        headers={
            "X-CSRF-Token": csrf_token,
            "Content-Type": "application/json",
        },
    )
    return client


@pytest.fixture
def root_client(db: Session) -> Client:
    """Client authenticated as root admin."""
    event, _ = create_test_event(db, name="Root Event")
    user = create_test_user(
        db, username="root.admin", display_name="Root Admin",
        is_root_admin=True, is_admin=True, event_id=None,
    )
    return _make_client(db, user)


@pytest.fixture
def admin_client(db: Session) -> Client:
    """Client authenticated as a regular admin (not root)."""
    event, _ = create_test_event(db, name="Admin Event")
    user = create_test_user(
        db, username="admin.user", display_name="Admin",
        is_admin=True, event_id=event.id,
    )
    return _make_client(db, user)


@pytest.fixture
def issuer_client(db: Session) -> tuple[Client, User, Event]:
    """Client authenticated as an issuer. Returns (client, user, event)."""
    event, _ = create_test_event(db, name="Issuer Event")
    user = create_test_user(
        db, username="issuer.user", display_name="Issuer",
        is_issuer=True, event_id=event.id,
    )
    return _make_client(db, user), user, event


@pytest.fixture
def user_client(db: Session) -> tuple[Client, User, Event]:
    """Client authenticated as a regular user. Returns (client, user, event)."""
    event, _ = create_test_event(db, name="User Event")
    user = create_test_user(
        db, username="regular.user", display_name="Regular User",
        event_id=event.id, can_edit=True,
    )
    return _make_client(db, user), user, event


@pytest.fixture
def reauth_admin_client(db: Session) -> Client:
    """Admin client with recent re-authentication (for destructive ops)."""
    event, _ = create_test_event(db, name="Reauth Event")
    user = create_test_user(
        db, username="reauth.admin", display_name="Reauth Admin",
        is_admin=True, event_id=event.id,
    )
    return _make_client(db, user, reauth=True)
