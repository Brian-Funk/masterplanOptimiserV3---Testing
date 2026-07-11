"""Regression tests for passkey challenge ceremony isolation."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from webauthn.helpers import bytes_to_base64url

from app.api.v1 import passkey as passkey_api
from app.core.activation import create_activation_link
from app.core.rate_limit import limiter
from app.models.user import PasskeyChallenge, WebAuthnCredential
from server_backend.conftest import _make_client, _raw_client, create_test_user


def _credential_id(value: str) -> bytes:
    return value.encode("utf-8")


def _raw_id(value: str) -> str:
    return bytes_to_base64url(_credential_id(value))


def _client_data(challenge: str) -> str:
    payload = json.dumps({"challenge": challenge}).encode("utf-8")
    return bytes_to_base64url(payload)


def _auth_body(credential_name: str, *, ceremony_id: int | None = None, challenge: str | None = None):
    body = {
        "id": _raw_id(credential_name),
        "rawId": _raw_id(credential_name),
        "type": "public-key",
        "response": {},
    }
    if ceremony_id is not None:
        body["ceremony_id"] = ceremony_id
    if challenge is not None:
        body["response"]["clientDataJSON"] = _client_data(challenge)
    return body


def _registration_body(*, ceremony_id: int | None = None, challenge: str | None = None):
    body = {
        "id": "new-credential",
        "rawId": "new-credential",
        "type": "public-key",
        "response": {},
    }
    if ceremony_id is not None:
        body["ceremony_id"] = ceremony_id
    if challenge is not None:
        body["response"]["clientDataJSON"] = _client_data(challenge)
    return body


def _install_auth_success(monkeypatch):
    def fake_verify_authentication_response(**kwargs):
        return SimpleNamespace(new_sign_count=kwargs["credential_current_sign_count"] + 1)

    monkeypatch.setattr(
        passkey_api,
        "verify_authentication_response",
        fake_verify_authentication_response,
    )


def _install_registration_success(monkeypatch, credential_id: bytes = b"new-cred"):
    def fake_verify_registration_response(**kwargs):
        return SimpleNamespace(
            credential_id=credential_id,
            credential_public_key=b"public-key",
            sign_count=0,
            aaguid=None,
        )

    monkeypatch.setattr(
        passkey_api,
        "verify_registration_response",
        fake_verify_registration_response,
    )


def _add_credential(db, user, credential_name: str):
    credential = WebAuthnCredential(
        user_id=user.id,
        credential_id=_credential_id(credential_name),
        public_key=b"public-key",
        sign_count=0,
    )
    db.add(credential)
    db.commit()
    return credential


def test_concurrent_login_ceremonies_do_not_invalidate_each_other(db, monkeypatch):
    """Two pending authentication challenges can complete independently."""
    user_a = create_test_user(db, username="login.a")
    user_b = create_test_user(db, username="login.b")
    _add_credential(db, user_a, "cred-a")
    _add_credential(db, user_b, "cred-b")
    _install_auth_success(monkeypatch)

    client = _raw_client()
    begin_a = client.post("/api/v1/passkey/auth/begin").json()
    begin_b = client.post("/api/v1/passkey/auth/begin").json()

    assert begin_a["ceremony_id"] != begin_b["ceremony_id"]
    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.challenge_type == "authentication").count() == 2

    complete_a = client.post(
        "/api/v1/passkey/auth/complete",
        json=_auth_body("cred-a", ceremony_id=begin_a["ceremony_id"]),
    )
    assert complete_a.status_code == 200

    complete_b = client.post(
        "/api/v1/passkey/auth/complete",
        json=_auth_body("cred-b", ceremony_id=begin_b["ceremony_id"]),
    )
    assert complete_b.status_code == 200
    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.challenge_type == "authentication").count() == 0


def test_auth_complete_without_ceremony_id_uses_client_data_challenge_fallback(db, monkeypatch):
    """Cached old frontend clients can still complete by the signed challenge value."""
    user = create_test_user(db, username="legacy.login")
    _add_credential(db, user, "legacy-cred")
    _install_auth_success(monkeypatch)

    client = _raw_client()
    begin = client.post("/api/v1/passkey/auth/begin").json()
    challenge = db.query(PasskeyChallenge).filter(PasskeyChallenge.id == begin["ceremony_id"]).one()

    complete = client.post(
        "/api/v1/passkey/auth/complete",
        json=_auth_body("legacy-cred", challenge=challenge.challenge),
    )
    assert complete.status_code == 200


def test_auth_complete_with_wrong_ceremony_fails_without_consuming_pending_challenge(db, monkeypatch):
    user = create_test_user(db, username="wrong.login")
    _add_credential(db, user, "wrong-cred")
    _install_auth_success(monkeypatch)

    client = _raw_client()
    begin = client.post("/api/v1/passkey/auth/begin").json()

    complete = client.post(
        "/api/v1/passkey/auth/complete",
        json=_auth_body("wrong-cred", ceremony_id=begin["ceremony_id"] + 999),
    )
    assert complete.status_code == 400
    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.id == begin["ceremony_id"]).count() == 1


def test_expired_auth_ceremony_fails_cleanly(db, monkeypatch):
    user = create_test_user(db, username="expired.login")
    _add_credential(db, user, "expired-cred")
    _install_auth_success(monkeypatch)

    client = _raw_client()
    begin = client.post("/api/v1/passkey/auth/begin").json()
    challenge = db.query(PasskeyChallenge).filter(PasskeyChallenge.id == begin["ceremony_id"]).one()
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    complete = client.post(
        "/api/v1/passkey/auth/complete",
        json=_auth_body("expired-cred", ceremony_id=begin["ceremony_id"]),
    )
    assert complete.status_code == 400


def test_registration_double_begin_consumes_only_matching_ceremony(db, monkeypatch):
    user = create_test_user(db, username="register.admin", is_admin=True)
    client = _make_client(db, user)
    _install_registration_success(monkeypatch, b"registered-cred")

    begin_first = client.post("/api/v1/passkey/register/begin").json()
    begin_second = client.post("/api/v1/passkey/register/begin").json()
    assert begin_first["ceremony_id"] != begin_second["ceremony_id"]

    complete = client.post(
        "/api/v1/passkey/register/complete",
        json=_registration_body(ceremony_id=begin_first["ceremony_id"]),
    )
    assert complete.status_code == 200
    assert db.query(PasskeyChallenge).filter(
        PasskeyChallenge.challenge_type == "registration",
        PasskeyChallenge.user_id == user.id,
    ).count() == 1


def test_activation_registration_ceremonies_complete_independently(db, monkeypatch):
    """Two activation devices keep independent registration challenges."""
    admin = create_test_user(db, username="activation.admin", is_admin=True)
    user = create_test_user(db, username="activation.user", is_activated=False)
    token, _ = create_activation_link(user.id, admin.id, db)
    db.commit()
    client = _raw_client()

    begin_first = client.post(
        f"/api/v1/passkey/register/begin?activation_token={token}",
    ).json()
    begin_second = client.post(
        f"/api/v1/passkey/register/begin?activation_token={token}",
    ).json()
    assert begin_first["ceremony_id"] != begin_second["ceremony_id"]

    _install_registration_success(monkeypatch, b"activation-cred-1")
    complete_first = client.post(
        f"/api/v1/passkey/register/complete?activation_token={token}",
        json=_registration_body(ceremony_id=begin_first["ceremony_id"]),
    )
    assert complete_first.status_code == 200
    assert db.query(PasskeyChallenge).filter(
        PasskeyChallenge.challenge_type == "registration",
        PasskeyChallenge.user_id == user.id,
    ).count() == 1

    _install_registration_success(monkeypatch, b"activation-cred-2")
    complete_second = client.post(
        f"/api/v1/passkey/register/complete?activation_token={token}",
        json=_registration_body(ceremony_id=begin_second["ceremony_id"]),
    )
    assert complete_second.status_code == 200
    assert db.query(PasskeyChallenge).filter(
        PasskeyChallenge.challenge_type == "registration",
        PasskeyChallenge.user_id == user.id,
    ).count() == 0


def test_registration_cannot_complete_with_another_users_ceremony(db, monkeypatch):
    user_a = create_test_user(db, username="register.a", is_admin=True)
    user_b = create_test_user(db, username="register.b", is_admin=True)
    client_a = _make_client(db, user_a)
    client_b = _make_client(db, user_b)
    _install_registration_success(monkeypatch)

    begin_b = client_b.post("/api/v1/passkey/register/begin").json()
    complete = client_a.post(
        "/api/v1/passkey/register/complete",
        json=_registration_body(ceremony_id=begin_b["ceremony_id"]),
    )

    assert complete.status_code == 400
    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.id == begin_b["ceremony_id"]).count() == 1


def test_used_registration_ceremony_cannot_be_reused(db, monkeypatch):
    user = create_test_user(db, username="reuse.admin", is_admin=True)
    client = _make_client(db, user)
    _install_registration_success(monkeypatch, b"reuse-cred")

    begin = client.post("/api/v1/passkey/register/begin").json()
    body = _registration_body(ceremony_id=begin["ceremony_id"])

    first = client.post("/api/v1/passkey/register/complete", json=body)
    second = client.post("/api/v1/passkey/register/complete", json=body)

    assert first.status_code == 200
    assert second.status_code in {400, 401}
    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.id == begin["ceremony_id"]).count() == 0




def test_ten_people_can_login_with_heavy_interleaving(db, monkeypatch):
    """Ten pending login ceremonies stay isolated and complete out of order."""
    _install_auth_success(monkeypatch)
    client = _raw_client()

    users = []
    begins = []
    for index in range(10):
        user = create_test_user(db, username=f"parallel.login.{index}")
        credential_name = f"parallel-cred-{index}"
        _add_credential(db, user, credential_name)
        users.append((user, credential_name))
        begins.append(client.post("/api/v1/passkey/auth/begin").json())

    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.challenge_type == "authentication").count() == 10
    assert len({begin["ceremony_id"] for begin in begins}) == 10

    # Complete in a deliberately non-FIFO order. Alternate modern ceremony_id
    # requests with old-client clientDataJSON fallback requests.
    completion_order = [6, 1, 8, 0, 9, 3, 5, 2, 7, 4]
    for position, user_index in enumerate(completion_order):
        # TestClient uses one synthetic remote address for every request. Reset
        # halfway so this remains a many-user ceremony-isolation regression, not
        # a per-IP rate-limit test.
        if position == 5:
            limiter.reset()

        _, credential_name = users[user_index]
        ceremony_id = begins[user_index]["ceremony_id"]
        challenge = db.query(PasskeyChallenge).filter(PasskeyChallenge.id == ceremony_id).one()

        if position % 3 == 0:
            body = _auth_body(credential_name, challenge=challenge.challenge)
        else:
            body = _auth_body(credential_name, ceremony_id=ceremony_id)

        complete = client.post("/api/v1/passkey/auth/complete", json=body)
        assert complete.status_code == 200, (user_index, complete.text)

    assert db.query(PasskeyChallenge).filter(PasskeyChallenge.challenge_type == "authentication").count() == 0
