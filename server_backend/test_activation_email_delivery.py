"""Secure activation email delivery and expiry policy tests."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.requests import Request

import app.api.v1.admin as admin_module
from app.core import runtime_settings
from app.core.activation import (
    ADDITIONAL_PASSKEY,
    INITIAL_SETUP,
    ActivationDeliveryInProgressError,
    create_activation_link,
    validate_activation_token,
)
from app.core.activation_email import ActivationMailError, recover_stale_deliveries
from app.models.user import ActivationEmailDelivery, ActivationLink
from server_backend.conftest import create_test_event, create_test_user, _make_client


class FakeMailer:
    """In-memory SMTP stand-in used by API tests."""

    def __init__(self, messages: list, errors: list[ActivationMailError] | None = None):
        self.messages = messages
        self.errors = errors or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def send(self, message):
        self.messages.append(message)
        if self.errors:
            raise self.errors.pop(0)


def _request() -> Request:
    """Return a minimal request suitable for audit metadata in direct tests."""

    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/admin/users/1/activation-email",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "scheme": "https",
        "server": ("localhost", 443),
    })


@pytest.fixture
def configured_mail(monkeypatch):
    """Configure a safe fake SMTP sender and capture generated messages."""

    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "token-user")
    monkeypatch.setattr(settings, "SMTP_TOKEN", "provider-token")
    monkeypatch.setattr(settings, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "access@example.com")
    monkeypatch.setattr(settings, "SMTP_FROM_NAME", "Masterplan Calendar")
    messages: list = []
    monkeypatch.setattr(
        admin_module,
        "ActivationMailer",
        lambda: FakeMailer(messages),
    )
    return messages


def test_single_user_email_contains_link_and_two_qr_parts(
    db,
    admin_client,
    configured_mail,
):
    """A per-user send returns no token while producing the complete MIME email."""

    event, _ = create_test_event(db, name="Email Event")
    user = create_test_user(
        db,
        username="email.target",
        display_name="Email Target",
        event_id=event.id,
        is_activated=False,
    )

    response = admin_client.post(
        f"/api/v1/admin/users/{user.id}/activation-email",
        json={},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "activation_url" not in response.json()
    assert "token" not in str(response.json()).lower()
    assert len(configured_mail) == 1
    message = configured_mail[0]
    assert message["Date"]
    assert "/activate#token=" in message.get_body(preferencelist=("plain",)).get_content()
    image_parts = [part for part in message.walk() if part.get_content_type() == "image/png"]
    assert len(image_parts) == 2
    assert {part.get_content_disposition() for part in image_parts} == {"inline", "attachment"}

    delivery = db.query(ActivationEmailDelivery).filter_by(user_id=user.id).one()
    link = db.query(ActivationLink).filter_by(user_id=user.id).one()
    assert delivery.status == "accepted"
    assert link.invalidated_at is None
    assert link.delivery_pending is False
    assert len(link.token_hash) == 64


def test_delivery_helper_commits_only_non_secret_metadata(
    db,
    configured_mail,
):
    """The shared single and batch delivery path works without HTTP transport."""

    event, _ = create_test_event(db, name="Direct Event")
    admin = create_test_user(
        db,
        username="direct.admin",
        event_id=event.id,
        is_admin=True,
    )
    user = create_test_user(
        db,
        username="direct.target",
        event_id=event.id,
        is_activated=False,
    )

    result = admin_module._send_user_activation_email(
        user=user,
        admin=admin,
        mailer=FakeMailer(configured_mail),
        request=_request(),
        purpose=INITIAL_SETUP,
        db=db,
    )

    assert result.status == "accepted"
    assert result.expires_at is not None
    assert configured_mail[0]["Date"]
    image_parts = [
        part
        for part in configured_mail[0].walk()
        if part.get_content_type() == "image/png"
    ]
    assert len(image_parts) == 2
    with Image.open(BytesIO(image_parts[0].get_payload(decode=True))) as qr_badge:
        assert qr_badge.format == "PNG"
        assert qr_badge.size == (640, 760)
    delivery = db.query(ActivationEmailDelivery).filter_by(user_id=user.id).one()
    assert delivery.status == "accepted"
    assert not hasattr(delivery, "activation_url")
    assert not hasattr(delivery, "token")


def test_additional_passkey_email_states_non_destructive_outcome(
    db,
    configured_mail,
):
    """Additional-passkey mail is purpose-bound and explains retained access."""

    event, _ = create_test_event(db, name="Additive Event")
    admin = create_test_user(
        db,
        username="additive.admin",
        event_id=event.id,
        is_admin=True,
    )
    user = create_test_user(
        db,
        username="additive.target",
        display_name="Additive Target",
        event_id=event.id,
        is_activated=True,
    )

    result = admin_module._send_user_activation_email(
        user=user,
        admin=admin,
        mailer=FakeMailer(configured_mail),
        request=_request(),
        purpose=ADDITIONAL_PASSKEY,
        db=db,
    )

    assert result.status == "accepted"
    assert result.purpose == ADDITIONAL_PASSKEY
    message = configured_mail[0]
    assert message["Subject"] == "Add another Masterplan Calendar passkey"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "existing passkeys and signed-in sessions will remain valid" in plain
    delivery = db.query(ActivationEmailDelivery).filter_by(user_id=user.id).one()
    link = db.query(ActivationLink).filter_by(user_id=user.id).one()
    assert delivery.purpose == ADDITIONAL_PASSKEY
    assert link.purpose == ADDITIONAL_PASSKEY


def test_unknown_delivery_is_recorded_and_link_is_invalidated(
    db,
    admin_client,
    configured_mail,
    monkeypatch,
):
    """An uncertain SMTP outcome never leaves a usable activation link."""

    event, _ = create_test_event(db, name="Unknown Event")
    user = create_test_user(
        db,
        username="unknown.target",
        event_id=event.id,
        is_activated=False,
    )
    monkeypatch.setattr(
        admin_module,
        "ActivationMailer",
        lambda: FakeMailer(
            configured_mail,
            [ActivationMailError("delivery_unknown", "Delivery unknown.", unknown=True)],
        ),
    )

    response = admin_client.post(
        f"/api/v1/admin/users/{user.id}/activation-email",
        json={},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    delivery = db.query(ActivationEmailDelivery).filter_by(user_id=user.id).one()
    link = db.query(ActivationLink).filter_by(user_id=user.id).one()
    assert delivery.error_code == "delivery_unknown"
    assert link.invalidated_at is not None


def test_retry_links_attempts_and_creates_a_fresh_token(
    db,
    admin_client,
    configured_mail,
    monkeypatch,
):
    """Retry creates a new link and records its relationship to the failed attempt."""

    event, _ = create_test_event(db, name="Retry Event")
    user = create_test_user(
        db,
        username="retry.target",
        event_id=event.id,
        is_activated=False,
    )
    errors = [ActivationMailError("recipient_rejected", "Recipient rejected.")]
    monkeypatch.setattr(
        admin_module,
        "ActivationMailer",
        lambda: FakeMailer(configured_mail, errors),
    )
    first = admin_client.post(
        f"/api/v1/admin/users/{user.id}/activation-email",
        json={},
    ).json()
    second = admin_client.post(
        f"/api/v1/admin/users/{user.id}/activation-email",
        json={"retry_of_delivery_id": first["delivery_id"]},
    ).json()

    assert first["status"] == "failed"
    assert second["status"] == "accepted"
    deliveries = (
        db.query(ActivationEmailDelivery)
        .filter_by(user_id=user.id)
        .order_by(ActivationEmailDelivery.id)
        .all()
    )
    links = (
        db.query(ActivationLink)
        .filter_by(user_id=user.id)
        .order_by(ActivationLink.id)
        .all()
    )
    assert deliveries[1].retry_of_id == deliveries[0].id
    assert links[0].token_hash != links[1].token_hash
    assert links[0].invalidated_at is not None
    assert links[1].invalidated_at is None


def test_batch_uses_only_selected_users_and_reports_missing_email(
    db,
    admin_client,
    configured_mail,
):
    """Batch email is explicit and returns an outcome for every selected user."""

    event, _ = create_test_event(db, name="Selected Event")
    selected = create_test_user(
        db,
        username="selected.target",
        event_id=event.id,
        is_activated=False,
    )
    missing = create_test_user(
        db,
        username="missing.target",
        event_id=event.id,
        is_activated=False,
    )
    unselected = create_test_user(
        db,
        username="unselected.target",
        event_id=event.id,
        is_activated=False,
    )
    missing.email = None
    db.commit()

    response = admin_client.post(
        "/api/v1/admin/batch-activation-emails",
        json={"user_ids": [selected.id, missing.id]},
    )

    assert response.status_code == 200
    assert [result["user_id"] for result in response.json()["results"]] == [
        selected.id,
        missing.id,
    ]
    assert response.json()["results"][0]["status"] == "accepted"
    assert response.json()["results"][1]["error_code"] == "missing_email"
    assert db.query(ActivationLink).filter_by(user_id=unselected.id).count() == 0


def test_activation_expiry_defaults_to_24_hours_and_is_capped(db):
    """The global policy advertises the secure default and seven-day maximum."""

    meta = runtime_settings.get_all(db)["activation_link_expiry_hours"]
    assert meta["default"] == 24
    assert meta["min"] == 1
    assert meta["max"] == 168


def test_root_can_invalidate_all_active_links_after_reauthentication(db):
    """Global invalidation is root-only, confirmed and audited."""

    event, _ = create_test_event(db, name="Invalidate Event")
    root = create_test_user(
        db,
        username="invalidate.root",
        is_root_admin=True,
        is_admin=True,
    )
    target = create_test_user(
        db,
        username="invalidate.target",
        event_id=event.id,
        is_activated=False,
    )
    client = _make_client(db, root, reauth=True)
    client.post(f"/api/v1/admin/users/{target.id}/activation-link", json={})

    response = client.post(
        "/api/v1/admin/activation-links/invalidate-all",
        json={"confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["invalidated_count"] == 1
    link = db.query(ActivationLink).filter_by(user_id=target.id).one()
    assert link.invalidated_at is not None
    assert link.invalidated_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)


def test_pending_delivery_link_cannot_be_used_until_smtp_acceptance(db):
    """A committed link remains unusable while its SMTP attempt is unresolved."""

    event, _ = create_test_event(db, name="Pending Event")
    admin = create_test_user(db, username="pending.admin", is_admin=True)
    user = create_test_user(
        db,
        username="pending.target",
        event_id=event.id,
        is_activated=False,
    )
    token, link = create_activation_link(
        user_id=user.id,
        created_by_id=admin.id,
        db=db,
        delivery_pending=True,
    )
    db.commit()

    assert validate_activation_token(token, db) is None
    link.delivery_pending = False
    db.commit()
    assert validate_activation_token(token, db).id == link.id


def test_interrupted_delivery_recovery_invalidates_pending_link(db):
    """An interrupted SMTP attempt becomes unknown and cannot leave a live link."""

    event, _ = create_test_event(db, name="Recovery Event")
    admin = create_test_user(db, username="recovery.admin", is_admin=True)
    user = create_test_user(
        db,
        username="recovery.target",
        event_id=event.id,
        is_activated=False,
    )
    _token, link = create_activation_link(
        user_id=user.id,
        created_by_id=admin.id,
        db=db,
        delivery_pending=True,
    )
    delivery = ActivationEmailDelivery(
        activation_link_id=link.id,
        user_id=user.id,
        requested_by_id=admin.id,
        recipient_email="recovery@example.com",
        status="sending",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db.add(delivery)
    db.commit()

    assert recover_stale_deliveries(db, user_id=user.id) == 1
    db.commit()
    db.refresh(delivery)
    db.refresh(link)
    assert delivery.status == "unknown"
    assert delivery.error_code == "delivery_interrupted"
    assert link.delivery_pending is False
    assert link.invalidated_at is not None


def test_existing_send_is_reported_without_creating_another_link(
    db,
    configured_mail,
):
    """A concurrent request is skipped while the first SMTP hand-off is active."""

    event, _ = create_test_event(db, name="Concurrent Event")
    admin = create_test_user(
        db,
        username="concurrent.admin",
        is_admin=True,
        event_id=event.id,
    )
    user = create_test_user(
        db,
        username="concurrent.target",
        event_id=event.id,
        is_activated=False,
    )
    user.email = "concurrent@example.com"
    db.commit()
    _token, link = create_activation_link(
        user_id=user.id,
        created_by_id=admin.id,
        db=db,
        delivery_pending=True,
    )
    delivery = ActivationEmailDelivery(
        activation_link_id=link.id,
        user_id=user.id,
        requested_by_id=admin.id,
        recipient_email=user.email,
        status="sending",
        started_at=datetime.now(timezone.utc),
    )
    db.add(delivery)
    db.commit()

    result = admin_module._send_user_activation_email(
        user=user,
        admin=admin,
        mailer=FakeMailer(configured_mail),
        request=_request(),
        purpose=INITIAL_SETUP,
        db=db,
    )

    assert result.status == "skipped"
    assert result.error_code == "delivery_in_progress"
    with pytest.raises(ActivationDeliveryInProgressError):
        create_activation_link(
            user_id=user.id,
            created_by_id=admin.id,
            db=db,
        )
    with pytest.raises(HTTPException) as invalidation:
        admin_module.invalidate_activation_link(
            user_id=user.id,
            link_id=link.id,
            request=_request(),
            admin=admin,
            db=db,
        )
    assert invalidation.value.status_code == 409
    assert db.query(ActivationLink).filter_by(user_id=user.id).count() == 1
    assert configured_mail == []
