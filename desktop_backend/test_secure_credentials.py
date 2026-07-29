"""Regression tests for desktop secure credential storage."""

import pytest

from app.core.google_credentials import (
    get_connection_token_data,
    persist_refreshed_connection_tokens,
    store_connection_token_secrets,
)
from app.core.secure_credentials import (
    SecureCredentialStoreUnavailable,
    google_access_token_key,
    google_oauth_client_secret_key,
    google_refresh_token_key,
    mp_backend_secret_key,
)
from app.models.app_settings import AppSettings
from app.models.google_calendar import GoogleCalendarConnection
from desktop_backend.conftest import create_test_event


def test_mp_backend_save_stores_secret_only_in_secure_store(
    db,
    client,
    secure_credential_store,
):
    event = create_test_event(db)

    response = client.put(
        f"/api/v1/mp-backend/?event_id={event.id}",
        json={
            "server_url": "https://mp.example.test",
            "publish_secret": "publish-secret-value",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["server_url"] == "https://mp.example.test"
    assert payload["secret_preview"] is None
    assert payload["secret_available"] is True
    db.refresh(event)
    assert event.mp_backend_url == "https://mp.example.test"
    assert "mp_backend_secret" not in event.__table__.columns
    assert (
        secure_credential_store.values[mp_backend_secret_key(event.id)]
        == "publish-secret-value"
    )


def test_missing_secure_mp_backend_secret_requires_reconnection(
    db,
    client,
    secure_credential_store,
):
    event = create_test_event(db)
    event.mp_backend_url = "https://mp.example.test"
    db.commit()

    response = client.get(f"/api/v1/mp-backend/?event_id={event.id}")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["server_url"] == "https://mp.example.test"
    assert response.json()["secret_available"] is False
    assert mp_backend_secret_key(event.id) not in secure_credential_store.values


def test_mp_backend_disconnect_deletes_secure_secret(db, client, secure_credential_store):
    event = create_test_event(db)
    event.mp_backend_url = "https://mp.example.test"
    secure_credential_store.values[mp_backend_secret_key(event.id)] = "secret"
    db.commit()

    response = client.delete(f"/api/v1/mp-backend/?event_id={event.id}")

    assert response.status_code == 200
    assert mp_backend_secret_key(event.id) not in secure_credential_store.values
    db.refresh(event)
    assert event.mp_backend_url is None


def test_secure_store_unavailable_blocks_connection_without_database_fallback(
    db,
    client,
    secure_credential_store,
):
    event = create_test_event(db)
    event.mp_backend_url = "https://mp.example.test"
    db.commit()
    secure_credential_store.is_available = False

    response = client.post(f"/api/v1/mp-backend/ping?event_id={event.id}")

    assert response.status_code == 503
    db.refresh(event)
    assert event.mp_backend_url == "https://mp.example.test"


def test_google_oauth_client_secret_is_stored_in_secure_store(
    db,
    client,
    secure_credential_store,
):
    response = client.put(
        "/api/v1/app-settings/google-oauth",
        json={"client_id": "google-client-id", "client_secret": "google-client-secret"},
    )

    assert response.status_code == 200
    id_row = db.query(AppSettings).filter(AppSettings.key == "google_client_id").one()
    assert id_row.value == "google-client-id"
    assert (
        db.query(AppSettings).filter(AppSettings.key == "google_client_secret").first()
        is None
    )
    assert (
        secure_credential_store.values[google_oauth_client_secret_key()]
        == "google-client-secret"
    )


def test_google_connection_secrets_are_split_from_token_metadata(
    db,
    secure_credential_store,
):
    connection = GoogleCalendarConnection(account_email="user@example.test", token_data={})
    db.add(connection)
    db.commit()
    db.refresh(connection)

    store_connection_token_secrets(
        connection,
        {
            "access_token": "access-token-value",
            "refresh_token": "refresh-token-value",
            "client_secret": "oauth-client-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "scopes": ["calendar"],
            "expiry": "2026-08-01T12:00:00",
        },
    )
    db.commit()
    db.refresh(connection)

    assert secure_credential_store.values[google_access_token_key(connection.id)] == "access-token-value"
    assert secure_credential_store.values[google_refresh_token_key(connection.id)] == "refresh-token-value"
    assert secure_credential_store.values[google_oauth_client_secret_key()] == "oauth-client-secret"
    assert "access_token" not in connection.token_data
    assert "refresh_token" not in connection.token_data
    assert "client_secret" not in connection.token_data
    assert connection.token_data["access_token_ref"] == google_access_token_key(connection.id)
    assert connection.token_data["refresh_token_ref"] == google_refresh_token_key(connection.id)


def test_legacy_google_token_data_requires_reconnection(db, secure_credential_store):
    connection = GoogleCalendarConnection(
        account_email="user@example.test",
        token_data={
            "access_token": "legacy-access",
            "refresh_token": "legacy-refresh",
            "client_secret": "legacy-client-secret",
            "client_id": "client-id",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)

    with pytest.raises(
        SecureCredentialStoreUnavailable,
        match="Retired database-stored Google credentials are unsupported",
    ):
        get_connection_token_data(db, connection)

    assert google_access_token_key(connection.id) not in secure_credential_store.values
    assert google_refresh_token_key(connection.id) not in secure_credential_store.values
    assert google_oauth_client_secret_key() not in secure_credential_store.values
    db.refresh(connection)
    assert connection.token_data["access_token"] == "legacy-access"
    assert connection.token_data["refresh_token"] == "legacy-refresh"
    assert connection.token_data["client_secret"] == "legacy-client-secret"


def test_google_oauth_callback_stores_tokens_in_secure_store(
    db,
    client,
    monkeypatch,
    secure_credential_store,
):
    import googleapiclient.discovery as discovery
    import app.api.v1.google as google_api

    monkeypatch.setattr(
        google_api,
        "exchange_code_for_token",
        lambda code, state: {
            "access_token": "callback-access",
            "refresh_token": "callback-refresh",
            "client_secret": "callback-client-secret",
            "client_id": "client-id",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["calendar"],
            "expiry": "2026-08-01T12:00:00",
        },
    )

    class FakeCalendarList:
        def get(self, calendarId):
            return self

        def execute(self):
            return {"id": "user@example.test"}

    class FakeService:
        def calendarList(self):
            return FakeCalendarList()

    monkeypatch.setattr(discovery, "build", lambda *args, **kwargs: FakeService())

    response = client.post(
        "/api/v1/google/oauth2callback",
        json={"code": "code", "state": "state"},
    )

    assert response.status_code == 200
    connection = db.query(GoogleCalendarConnection).one()
    assert connection.account_email == "user@example.test"
    assert secure_credential_store.values[google_access_token_key(connection.id)] == "callback-access"
    assert secure_credential_store.values[google_refresh_token_key(connection.id)] == "callback-refresh"
    assert secure_credential_store.values[google_oauth_client_secret_key()] == "callback-client-secret"
    assert "access_token" not in connection.token_data
    assert "refresh_token" not in connection.token_data
    assert "client_secret" not in connection.token_data


def test_google_token_refresh_updates_secure_store_and_expiry(
    db,
    secure_credential_store,
):
    connection = GoogleCalendarConnection(account_email="user@example.test", token_data={})
    db.add(connection)
    db.commit()
    db.refresh(connection)
    store_connection_token_secrets(
        connection,
        {
            "access_token": "old-access",
            "refresh_token": "refresh",
            "client_secret": "client-secret",
            "client_id": "client-id",
        },
    )
    db.commit()

    persist_refreshed_connection_tokens(
        db,
        connection,
        {
            "access_token": "new-access",
            "refresh_token": "refresh",
            "client_secret": "client-secret",
            "client_id": "client-id",
            "expiry": "2026-08-01T13:00:00",
        },
    )

    assert secure_credential_store.values[google_access_token_key(connection.id)] == "new-access"
    db.refresh(connection)
    assert connection.token_data["expiry"] == "2026-08-01T13:00:00"
    assert "access_token" not in connection.token_data


def test_export_does_not_include_secret_values(
    db,
    client,
    secure_credential_store,
):
    event = create_test_event(db)
    event.mp_backend_url = "https://mp.example.test"
    secure_credential_store.values[mp_backend_secret_key(event.id)] = "publish-secret-value"
    db.commit()

    response = client.post(
        "/api/v1/data/export",
        json={"scope": "event", "event_ids": [event.id]},
    )

    assert response.status_code == 200
    encoded = response.text
    assert "publish-secret-value" not in encoded
    assert "mp_backend_secret" not in encoded
