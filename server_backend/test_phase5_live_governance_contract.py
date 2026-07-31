"""Independent Phase 5 live-governance and Desktop bridge contracts."""

import json
import os
from pathlib import Path

from server_backend.conftest import _make_client, create_test_user


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = Path(os.environ.get(
    "MP_OPT_SERVER_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - Server" / "MasterplanOptimiserV3---Server",
))
APP_ROOT = Path(os.environ.get(
    "MP_OPT_APP_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - App" / "masterplanOptimiserV3 - App",
))

CONFIRMATION = {
    "authorised_to_configure": True,
    "reviewed_generated_documents": True,
    "confirmed_permitted_data_policy": True,
    "understands_no_legal_certification": True,
}


def _profile():
    return {
        "controller_type": "organisation",
        "controller_legal_name": "Synthetic Controller",
        "controller_postal_address": "Controller Street 1, 8000 Zurich",
        "controller_country": "CH",
        "privacy_contact_email": "privacy@synthetic-controller.ch",
        "privacy_contact_phone": None,
        "dpo_contact": None,
        "supervisory_authority_name": "Federal Data Protection and Information Commissioner",
        "supervisory_authority_url": "https://www.edoeb.admin.ch/",
        "default_locale": "en",
        "processor_summary": "The enabled providers are listed below.",
        "retention_summary": "Controller-selected periods are listed below.",
        "rights_summary": "Contact the controller to exercise applicable rights.",
        "terms_summary": "Use is limited to authorised operational scheduling.",
        "structured": {
            "instance_name": "Synthetic Phase 5 instance",
            "supported_locales": ["en"],
            "jurisdiction_scope": "The controller recorded its own Swiss and European scope assessment.",
            "processing_purposes": [{
                "purpose_code": "event_scheduling",
                "enabled": True,
                "description": "Create operational schedules.",
                "gdpr_legal_basis": "Controller-recorded legitimate-interest assessment",
                "swiss_justification_or_basis": "Controller-recorded operational assessment",
                "required_or_optional": "required",
            }],
            "data_categories": [{
                "category_code": "operational_identity",
                "display_name": "Names and operational roles",
                "enabled": True,
                "required_or_optional": "required",
                "visibility": "participant",
                "source": "Controller and participant",
                "purpose_codes": ["event_scheduling"],
                "retention_policy_code": "instance_default",
                "sensitive_data_supported": False,
            }],
            "processors": [{
                "provider_code": "vps",
                "display_name": "Synthetic VPS",
                "service": "Hosting",
                "role": "processor",
                "purpose_codes": ["event_scheduling"],
                "data_categories": ["operational_identity"],
                "hosting_countries": ["CH"],
                "support_access_countries": ["CH"],
                "dpa_status": "accepted",
                "dpa_version": "synthetic-1",
                "transfer_mechanism": "No international transfer recorded",
                "public_notice_summary": "Hosts this synthetic instance in Switzerland.",
                "internal_notes_reference": "root-only-contract-reference",
                "enabled": True,
            }],
            "hosting_countries": ["CH"],
            "retention": {
                "policy_code": "instance_default",
                "live_retention_days": 30,
                "event_grace_days": 7,
                "backup_retention_days": 30,
                "audit_retention_days": 90,
                "receipt_retention_days": 365,
                "browser_cache_expiry_hours": 24,
                "automatic_purge_enabled": True,
                "legal_hold_supported": True,
            },
            "optional_features": {
                "smtp_enabled": False,
                "push_enabled": False,
                "offline_schedule_enabled": False,
                "public_schedule_enabled": True,
                "external_support_enabled": False,
                "ha_enabled": False,
                "dns_mode": "dns_only",
                "backup_storage_mode": "manual_portable",
            },
            "rights_request_url": "https://synthetic-controller.invalid/rights",
            "incident_contact_email": "incident@synthetic-controller.ch",
        },
    }


def _root_client(db):
    root = create_test_user(
        db, username="phase5.root", display_name="Phase 5 Root",
        is_root_admin=True, is_admin=True,
    )
    return _make_client(db, root, reauth=True)


def test_publication_uses_exact_runtime_conditioned_and_public_safe_snapshot(db):
    client = _root_client(db)
    saved = client.put("/api/v1/admin/governance", json=_profile())
    assert saved.status_code == 200
    assert saved.json()["preflight"]["ready"] is True
    published = client.post("/api/v1/admin/governance/publish", json=CONFIRMATION)
    assert published.status_code == 200

    public = client.get("/api/v1/governance/public").json()
    codes = {item["code"] for item in public["feature_disclosures"]}
    assert "public_schedule" in codes
    assert "offline_schedule" not in codes
    assert "push_notifications" not in codes
    assert "activation_email" not in codes
    assert "manual_activation" in codes
    assert "dns_only_routing" in codes
    assert "offline_schedule" not in public["storage"]
    assert "internal_notes_reference" not in json.dumps(public)
    assert "root-only-contract-reference" not in json.dumps(public)
    assert public["retention"]["event_grace_days"] == 7
    assert len(public["content_sha256"]) == 64


def test_draft_preview_does_not_mutate_published_content_and_exports_exact_version(db):
    client = _root_client(db)
    client.put("/api/v1/admin/governance", json=_profile())
    first = client.post("/api/v1/admin/governance/publish", json=CONFIRMATION).json()
    changed = _profile()
    changed["structured"]["optional_features"]["public_schedule_enabled"] = False
    client.put("/api/v1/admin/governance", json=changed)

    preview = client.get("/api/v1/admin/governance/preview").json()
    assert preview["diff"]["material_change"] is True
    assert any(change["path"].endswith("public_schedule_enabled") for change in preview["diff"]["changes"])
    assert client.get("/api/v1/governance/public").json()["content_sha256"] == first["content_sha256"]
    exported = client.get("/api/v1/admin/governance/export/1").json()
    assert exported["content_sha256"] == first["content_sha256"]
    assert exported["source_sha256"] == first["source_sha256"]
    assert exported["source_configuration"]["structured"]["processors"][0]["internal_notes_reference"] == "root-only-contract-reference"
    assert exported["published_content"]["optional_features"]["public_schedule_enabled"] is True


def test_schema_activation_and_desktop_bridge_are_bound_to_phase5_identity():
    migration = (SERVER_ROOT / "deploy/migrations/20260731_live_governance_phase5.sql").read_text(encoding="utf-8")
    governance_api = (SERVER_ROOT / "backend/app/api/v1/governance.py").read_text(encoding="utf-8")
    activation = (SERVER_ROOT / "backend/app/core/activation_email.py").read_text(encoding="utf-8")
    desktop_bridge = (APP_ROOT / "backend/app/api/v1/mp_backend.py").read_text(encoding="utf-8")
    desktop_notice = (APP_ROOT / "web/src/components/PermittedDataInputNotice.tsx").read_text(encoding="utf-8")
    licence_page = (SERVER_ROOT / "web/src/app/licence/page.tsx").read_text(encoding="utf-8")
    notices_page = (SERVER_ROOT / "web/src/app/third-party-notices/page.tsx").read_text(encoding="utf-8")
    security_page = (SERVER_ROOT / "web/src/app/security/page.tsx").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS structured_json" in migration
    assert "CREATE TABLE IF NOT EXISTS event_governance_overrides" in migration
    assert "require_root_recent_reauth" in governance_api
    assert "understands_no_legal_certification: Literal[True]" in governance_api
    assert "policy_url=policy_url" in activation
    for field in ("privacy_url", "retention_days", "enabled_optional_features", "incident_contact"):
        assert f'"{field}"' in desktop_bridge
    assert "Controller-selected event retention grace" in desktop_notice
    assert "View the exact privacy notice" in desktop_notice
    assert '"LICENSE"' in licence_page
    assert '"THIRD-PARTY-NOTICES.md"' in notices_page
    assert '"SECURITY.md"' in security_page
    assert "SECURITY_REPORT.md" not in security_page
