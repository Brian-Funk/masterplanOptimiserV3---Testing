"""Phase D cross-repository session and browser-storage assurance."""

from __future__ import annotations

import json
import os
from pathlib import Path


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = Path(os.environ.get(
    "MP_OPT_SERVER_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - Server" / "MasterplanOptimiserV3---Server",
))
DOCS_ROOT = Path(os.environ.get(
    "MP_OPT_DOCS_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - Docs" / "mp-opt-info",
))
CONTRACT_PATH = SERVER_ROOT / "deploy" / "security" / "session_storage_contract.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_session_matrix_is_complete_and_bound_to_runtime_configuration():
    contract = _contract()
    assert contract["format"] == "masterplan-session-storage-contract-v1"
    selections = {item["runtime_key"]: item for item in contract["controller_selections"]}
    assert set(selections) == {
        "session_ttl_hours",
        "session_ttl_hours_admin",
        "session_inactivity_minutes",
        "reauth_window_minutes",
        "offline_access_ttl_hours",
    }
    assert all(item["minimum"] <= item["default"] <= item["maximum"] for item in selections.values())
    assert contract["controller_confirmation_required"] is True

    runtime_source = (SERVER_ROOT / "backend/app/core/runtime_settings.py").read_text(encoding="utf-8")
    session_source = (SERVER_ROOT / "backend/app/core/sessions.py").read_text(encoding="utf-8")
    security_source = (SERVER_ROOT / "backend/app/core/security.py").read_text(encoding="utf-8")
    for key in selections:
        assert f'"{key}"' in runtime_source
    assert "now > expires_at" in session_source
    assert "now > inactivity_limit" in session_source
    assert "AuthSession.revoked_at.is_(None)" in session_source
    assert "reauth_at + timedelta(minutes=window)" in security_source


def test_cookie_csrf_revocation_and_reauthentication_have_deterministic_server_tests():
    contract = _contract()
    cookie_profiles = {item["id"]: item for item in contract["production_cookie_profile"]}
    assert cookie_profiles["session"] == {
        "id": "session",
        "setting": "SESSION_COOKIE_NAME",
        "generated_name": "__Host-mp_session",
        "secure": True,
        "http_only": True,
        "same_site": "lax",
        "path": "/",
        "domain": None,
        "max_age_source": "server_session_absolute_expiry",
        "server_storage": "sha256_digest_only",
    }
    assert cookie_profiles["csrf"]["generated_name"] == "__Host-mp_csrf"
    assert cookie_profiles["csrf"]["http_only"] is False
    assert contract["csrf"]["write_methods"] == ["DELETE", "PATCH", "POST", "PUT"]

    tests = (SERVER_ROOT / "server_backend/test_phase_d_session_storage_contract.py").read_text(encoding="utf-8")
    for evidence in (
        "test_generated_production_cookie_profile_has_host_prefix_and_exact_attributes",
        "test_csrf_policy_matches_the_enforced_write_boundary",
        "test_absolute_inactivity_and_revocation_transitions_deny_access",
        "test_recent_reauthentication_window_is_inclusive_then_fails_closed",
    ):
        assert evidence in tests


def test_each_supported_browser_store_has_bounded_lifecycle_and_regression_evidence():
    contract = _contract()
    stores = {item["id"]: item for item in contract["browser_stores"]}
    assert set(stores) == {
        "cookies",
        "localStorage",
        "sessionStorage",
        "browser_history",
        "IndexedDB",
        "Cache API",
    }
    for item in stores.values():
        assert item["keys"]
        assert item["content"]
        assert item["created"]
        assert item["removed"]
        assert item["retention"]

    web_tests = SERVER_ROOT / "web/tests"
    for filename in (
        "apiFetch.test.ts",
        "AuthContext.test.tsx",
        "offlineAccess.test.ts",
        "offlineCalendarCache.test.ts",
        "routeSecret.test.ts",
        "serviceWorker.test.ts",
    ):
        assert (web_tests / filename).is_file(), filename

    worker = (SERVER_ROOT / "web/public/sw.js").read_text(encoding="utf-8")
    assert "mp-opt-app-__MP_OPT_RELEASE__" in worker
    assert 'url.pathname.startsWith("/api/")' not in worker
    assert "cache.put(event.request" not in worker


def test_public_disclosures_match_application_control_and_external_boundaries():
    contract = _contract()
    security_page = (
        DOCS_ROOT / "src/app/docs/advanced/security-model/page.tsx"
    ).read_text(encoding="utf-8")
    privacy_page = (DOCS_ROOT / "src/app/privacy/page.tsx").read_text(encoding="utf-8")
    inventory = (DOCS_ROOT / "docs/compliance/storage-inventory.md").read_text(encoding="utf-8")
    generated_notice = (
        SERVER_ROOT / "backend/app/core/governance_rendering.py"
    ).read_text(encoding="utf-8")

    for phrase in (
        "Regular sessions default to 8 hours",
        "privileged sessions default to 1 hour",
        "30-minute inactivity timeout",
        "five minutes",
        "Authenticated API responses are never written to the Cache API",
    ):
        assert phrase in security_page
    assert "controller must confirm the selected values" in security_page
    assert "does not prove physical deletion" in security_page
    assert "browser or device backup" in privacy_page
    assert "outside application control" in privacy_page
    assert "A signed controller or provider attestation records an assertion" in inventory
    for phrase in (
        "SESSION_COOKIE_NAME",
        "CSRF_COOKIE_NAME",
        "SESSION_TTL_HOURS",
        "Cache API stores only a versioned static application shell",
        "localStorage may retain theme",
        "sessionStorage and browser history may temporarily retain",
        "Optional IndexedDB offline calendar response data",
    ):
        assert phrase in generated_notice
    assert contract["external_boundaries"]
