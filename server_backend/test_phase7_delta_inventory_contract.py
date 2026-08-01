"""Independent Phase 7 technical data-inventory contracts."""

import json
import os
from pathlib import Path
import re
import pytest

from server_backend.conftest import app
from repo_roots import app_root, optional_docs_root, server_root


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = server_root()
APP_ROOT = app_root()
DOCS_ROOT = optional_docs_root()
pytestmark = pytest.mark.skipif(
    DOCS_ROOT is None,
    reason="project-site contracts require an explicit valid MP_OPT_DOCS_ROOT",
)
MANIFEST_PATH = (
    DOCS_ROOT / "docs/compliance/inventory-manifest.json"
    if DOCS_ROOT is not None
    else Path("project-site-not-configured")
)
FIXTURE_PATH = Path(__file__).parent / "fixtures/phase7_evidence_receipt.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _response_schema_name(openapi, snapshot):
    operation = openapi["paths"][snapshot["path"]][snapshot["method"]]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    return schema["$ref"].rsplit("/", 1)[-1]


def _matches(boundary, path):
    return (
        path in boundary["exact_paths"]
        or any(path.startswith(prefix) for prefix in boundary["path_prefixes"])
    )


def test_required_phase7_documents_and_machine_readable_inventory_exist():
    for relative in (
        "docs/compliance/data-inventory.md",
        "docs/compliance/data-flow-map.md",
        "docs/compliance/processing-activities-template.md",
        "docs/compliance/storage-inventory.md",
        "docs/compliance/inventory-manifest.json",
    ):
        assert (DOCS_ROOT / relative).is_file(), relative

    manifest = _manifest()
    assert manifest["schema_version"] == 1
    assert manifest["baseline"] == {
        "date": "2026-07-31",
        "server_sha": "c3779f10b6c04e44c9c8539d01a9919e18c373b8",
        "app_sha": "3f189cb52f39bf0602ceb677fa9430c938442344",
        "testing_sha": "bf53c08a3d0ca1b6f091dcdd9d795236ecf5cfbf",
        "docs_sha": "2272f64d594775ad4bc628ab9bbed73b08b1104b",
    }


def test_every_live_openapi_response_has_one_inventory_boundary():
    manifest = _manifest()
    boundaries = manifest["api_response_boundaries"]
    openapi = app.openapi()
    actual = {
        (method, path)
        for path, operations in openapi["paths"].items()
        for method in operations
        if method in HTTP_METHODS
    }
    assert len(actual) >= 120

    failures = []
    for method, path in sorted(actual):
        matches = [item["id"] for item in boundaries if _matches(item, path)]
        if len(matches) != 1:
            failures.append({"method": method, "path": path, "matches": matches})
    assert failures == []


def test_participant_offline_and_public_schema_snapshots_match_openapi():
    manifest = _manifest()
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]

    for name, snapshot in manifest["schema_snapshots"].items():
        assert _response_schema_name(openapi, snapshot) == snapshot["response_schema"], name
        response = schemas[snapshot["response_schema"]]
        assert sorted(response["properties"]) == snapshot["fields"], name
        if "nested_schema" in snapshot:
            nested = schemas[snapshot["nested_schema"]]
            assert sorted(nested["properties"]) == snapshot["nested_fields"], name
            for field in snapshot.get("null_only_fields", []):
                assert nested["properties"][field] == {
                    "type": "null",
                    "title": " ".join(word.capitalize() for word in field.split("_")),
                }


def test_every_storage_location_has_retention_deletion_and_reciprocal_categories():
    manifest = _manifest()
    categories = {item["id"]: item for item in manifest["data_categories"]}
    storage = {item["id"]: item for item in manifest["storage_locations"]}
    required = {
        "server_postgresql", "browser_cookies", "browser_session_storage",
        "browser_indexeddb", "browser_cache_api", "desktop_sqlite",
        "desktop_exports", "desktop_temporary", "system_logs",
        "encrypted_backups", "ha_replication", "evidence_ledger",
        "controller_evidence_git",
    }
    assert required <= storage.keys()
    for location in storage.values():
        assert location["retention_rule"].strip()
        assert location["deletion_trigger"].strip()
        assert location["controller_action"].strip()
        for category in location["data_categories"]:
            assert location["id"] in categories[category]["storage_locations"]


def test_inventory_references_current_server_and_desktop_storage_controls():
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    server_config = (SERVER_ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
    offline_cache = (SERVER_ROOT / "web/src/lib/offlineCalendarCache.ts").read_text(encoding="utf-8")
    service_worker = (SERVER_ROOT / "web/public/sw.js").read_text(encoding="utf-8")
    desktop_storage = (APP_ROOT / "docs/workstation-storage-security.md").read_text(encoding="utf-8")
    desktop_keys = (APP_ROOT / "backend/app/core/operator_evidence.py").read_text(encoding="utf-8")

    for setting in (
        "RETENTION_REVOKED_SESSIONS_DAYS",
        "EVENT_PURGE_GRACE_DAYS",
        "EVIDENCE_TOMBSTONE_RETENTION_DAYS",
        "COMPLIANCE_REQUEST_DIR",
        "HA_REPLICATION_REQUEST_DIR",
    ):
        assert setting in server_config
    assert "DB_VERSION = 3" in offline_cache
    assert "caches.open" in service_worker
    for category in (
        "desktop_database",
        "user_exports_and_diagnostics",
        "operator_backups_and_cloud_copies",
        "synthetic_test_temporary_data",
    ):
        assert category in desktop_storage
    assert "operating system credential store" in desktop_keys
    for inventory_id in (
        "browser_indexeddb", "browser_cache_api", "desktop_sqlite",
        "desktop_exports", "desktop_temporary", "os_credential_store",
        "server_runtime_files",
    ):
        assert f'"{inventory_id}"' in manifest_text


def test_synthetic_evidence_fixture_is_non_identifying():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    encoded = json.dumps(fixture, sort_keys=True)
    forbidden_keys = {
        "name", "first_name", "last_name", "email", "username",
        "task_title", "task_description", "schedule_data", "private_key",
        "session_token", "csrf_token", "ip_address",
    }
    assert forbidden_keys.isdisjoint(fixture)
    assert re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", encoded, re.I) is None
    assert re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", encoded) is None
    assert all("Synthetic Person" not in value for value in fixture.values() if isinstance(value, str))


def test_controller_facts_and_non_certification_boundaries_remain_explicit():
    manifest = _manifest()
    assert len(manifest["controller_confirmed_facts"]) >= 6
    assert "not a finding of legal compliance" in manifest["status_meaning"]
    assert "must_not_override" in manifest["privacy_page_feed"]
    for relative in (
        "data-inventory.md",
        "data-flow-map.md",
        "processing-activities-template.md",
        "storage-inventory.md",
    ):
        text = (DOCS_ROOT / "docs/compliance" / relative).read_text(encoding="utf-8")
        assert "\u2013" not in text and "\u2014" not in text
        assert "controller" in text.lower()
