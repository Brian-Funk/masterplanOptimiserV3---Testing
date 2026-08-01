"""Phase B disclosure snapshots and fail-closed legal-claim contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.governance_rendering import build_publication_payload, governance_preflight
from app.models.governance import GovernancePublication, InstanceGovernanceProfile
from server_backend.conftest import app
from repo_roots import app_root, optional_docs_root, server_root


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = server_root()
APP_ROOT = app_root()
DOCS_ROOT = optional_docs_root()
TESTING_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
CLAIM_FIXTURE = FIXTURE_ROOT / "phase_b_claims.json"
SNAPSHOT_PATH = FIXTURE_ROOT / "phase_b_governance_snapshot.json"
SERVER_POLICY = SERVER_ROOT / "deploy/security/legal_claim_rules.json"
DOCS_POLICY = (
    DOCS_ROOT / "docs/compliance/legal-claim-rules.json"
    if DOCS_ROOT is not None
    else None
)
SECURITY_TOOLS = SERVER_ROOT / "deploy/security"
if str(SECURITY_TOOLS) not in sys.path:
    sys.path.insert(0, str(SECURITY_TOOLS))

from legal_claim_lint import audit_public_claims, load_policy, scan_text, verify_fixture  # noqa: E402


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


SNAPSHOT = _json(SNAPSHOT_PATH)
FEATURE_ORDER = SNAPSHOT["feature_order"]


def _feature_state(bits: tuple[bool, ...]) -> dict[str, object]:
    state = dict(zip(FEATURE_ORDER, bits, strict=True))
    state.update({
        "smtp_provider_code": "smtp" if state["smtp_enabled"] else None,
        "push_provider_codes": ["push"] if state["push_enabled"] else [],
        "dns_mode": "dns_only",
        "backup_storage_mode": "controller_managed" if state["ha_enabled"] else "manual_portable",
    })
    return state


def _purpose(code: str, description: str) -> dict[str, object]:
    return {
        "purpose_code": code,
        "enabled": True,
        "description": description,
        "gdpr_legal_basis": "Controller-recorded synthetic assessment",
        "swiss_justification_or_basis": "Controller-recorded synthetic assessment",
        "required_or_optional": "required" if code in {"event_scheduling", "account_authentication"} else "optional",
        "withdrawal_effect": "The optional feature stops." if code not in {"event_scheduling", "account_authentication"} else None,
    }


def _processor(code: str, service: str, purpose: str) -> dict[str, object]:
    return {
        "provider_code": code,
        "display_name": f"Synthetic {service}",
        "service": service,
        "role": "processor",
        "purpose_codes": [purpose],
        "data_categories": ["operational_identity"],
        "hosting_countries": ["CH"],
        "support_access_countries": ["CH"],
        "dpa_status": "accepted",
        "dpa_version": "synthetic-1",
        "transfer_mechanism": "Controller-recorded synthetic assessment",
        "public_notice_summary": f"Provides synthetic {service.lower()} for this test profile.",
        "internal_notes_reference": "private-synthetic-reference",
        "enabled": True,
    }


def _profile(controller_type: str, bits: tuple[bool, ...]) -> InstanceGovernanceProfile:
    controller = SNAPSHOT["controller_profiles"][controller_type]
    features = _feature_state(bits)
    purposes = [
        _purpose("event_scheduling", "Create operational schedules."),
        _purpose("account_authentication", "Authenticate authorised users."),
    ]
    processors = [_processor("vps", "VPS hosting", "event_scheduling")]
    feature_purposes = (
        ("smtp_enabled", "activation_email", "Deliver activation messages.", "smtp", "SMTP delivery"),
        ("push_enabled", "push_notifications", "Deliver optional notifications.", "push", "Push delivery"),
        ("offline_schedule_enabled", "offline_schedule", "Store an optional bounded offline schedule.", None, None),
        ("public_schedule_enabled", "public_schedule", "Publish an optional bearer-link schedule.", None, None),
        ("external_support_enabled", "support", "Provide time-bounded authorised support.", "support", "Support access"),
        ("ha_enabled", "backup_and_recovery", "Maintain controller-configured recovery copies.", None, None),
    )
    for feature, purpose, description, processor_code, service in feature_purposes:
        if features[feature]:
            purposes.append(_purpose(purpose, description))
            if processor_code:
                processors.append(_processor(processor_code, service, purpose))
    structured = {
        "instance_name": f"Synthetic {controller_type} instance",
        "dpo_name_or_role": "Synthetic DPO" if controller_type == "organisation" else None,
        "eu_representative": controller["eu_representative"],
        "swiss_representative": controller["swiss_representative"],
        "supported_locales": ["en"],
        "jurisdiction_scope": "Controller-recorded synthetic Swiss and European scope assessment.",
        "processing_purposes": purposes,
        "data_categories": [{
            "category_code": "operational_identity",
            "display_name": "Names and operational roles",
            "enabled": True,
            "required_or_optional": "required",
            "visibility": "participant",
            "source": "Controller and participant",
            "purpose_codes": [item["purpose_code"] for item in purposes],
            "retention_policy_code": "instance_default",
            "sensitive_data_supported": False,
        }],
        "processors": processors,
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
        "optional_features": features,
        "rights_request_url": "https://synthetic-controller.invalid/rights",
        "incident_contact_email": "incident@synthetic-controller.invalid",
    }
    return InstanceGovernanceProfile(
        id=1,
        instance_id=f"00000000-0000-4000-8000-{controller_type[:3]}{sum(1 << index for index, bit in enumerate(bits) if bit):09d}"[:36],
        controller_type=controller["controller_type"],
        controller_legal_name=controller["controller_legal_name"],
        controller_postal_address=controller["controller_postal_address"],
        controller_country=controller["controller_country"],
        privacy_contact_email=controller["privacy_contact_email"],
        privacy_contact_phone=controller["privacy_contact_phone"],
        dpo_contact=controller["dpo_contact"],
        supervisory_authority_name="Synthetic supervisory authority",
        supervisory_authority_url="https://authority.invalid/",
        default_locale="en",
        processor_summary="The enabled synthetic providers are listed below.",
        retention_summary="Controller-selected synthetic periods are listed below.",
        rights_summary="Contact the synthetic controller to exercise applicable rights.",
        terms_summary="Use is limited to authorised synthetic operational scheduling.",
        structured_json=json.dumps(structured, sort_keys=True),
    )


def _expected_codes(features: dict[str, object]) -> list[str]:
    codes = ["activation_email" if features["smtp_enabled"] else "manual_activation"]
    for feature, code in (
        ("push_enabled", "push_notifications"),
        ("offline_schedule_enabled", "offline_schedule"),
        ("public_schedule_enabled", "public_schedule"),
        ("external_support_enabled", "external_support"),
        ("ha_enabled", "high_availability"),
    ):
        if features[feature]:
            codes.append(code)
    codes.append("dns_only_routing")
    return codes


def test_shared_claim_policy_and_fixture_corpus_fail_closed():
    if DOCS_POLICY is not None:
        assert _json(SERVER_POLICY) == _json(DOCS_POLICY)
    policy = load_policy(SERVER_POLICY)
    assert verify_fixture(CLAIM_FIXTURE, policy) == []
    fixture = _json(CLAIM_FIXTURE)
    for item in fixture["unsafe"]:
        assert item["rule_id"] in {finding["rule_id"] for finding in scan_text(item["text"], policy)}
    if DOCS_ROOT is not None:
        completed = subprocess.run(
            ["node", "scripts/check-legal-claims.mjs", "--fixture", str(CLAIM_FIXTURE)],
            cwd=DOCS_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_current_public_outputs_pass_the_shared_claim_policy():
    roots = [
        (SERVER_ROOT, "server"),
        (APP_ROOT, "app"),
        (TESTING_ROOT, "testing"),
    ]
    if DOCS_ROOT is not None:
        roots.append((DOCS_ROOT, "docs"))
    for root, profile in roots:
        assert audit_public_claims(root, profile, SERVER_POLICY) == [], profile


def test_all_128_controller_feature_payload_snapshots():
    observed_catalog: dict[str, str] = {}
    count = 0
    for controller_type in SNAPSHOT["controller_profiles"]:
        controller = SNAPSHOT["controller_profiles"][controller_type]
        for bits in product((False, True), repeat=len(FEATURE_ORDER)):
            count += 1
            profile = _profile(controller_type, bits)
            payload = build_publication_payload(profile)
            features = _feature_state(bits)
            for key, value in controller.items():
                assert payload[key] == value, (controller_type, bits, key)
            codes = [item["code"] for item in payload["feature_disclosures"]]
            assert codes == _expected_codes(features), (controller_type, bits)
            for item in payload["feature_disclosures"]:
                observed_catalog[item["code"]] = item["text"]
            assert ("offline_schedule" in payload["storage"]) is features["offline_schedule_enabled"]
            processor_codes = {item["provider_code"] for item in payload["processors"]}
            assert ("smtp" in processor_codes) is features["smtp_enabled"]
            assert ("push" in processor_codes) is features["push_enabled"]
            assert ("support" in processor_codes) is features["external_support_enabled"]
            assert "internal_notes_reference" not in json.dumps(payload)
    assert count == 128
    assert observed_catalog == SNAPSHOT["feature_disclosures"]


def test_all_128_controller_feature_scenarios_render_every_public_section(db):
    publication = GovernancePublication(
        version=1,
        content_json="{}",
        content_sha256="0" * 64,
        source_json="{}",
        source_sha256="0" * 64,
        published_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        material_change=True,
        change_summary_json="[]",
    )
    db.add(publication)
    db.commit()
    client = TestClient(app)
    catalog = SNAPSHOT["feature_disclosures"]
    rendered = 0
    for controller_type in SNAPSHOT["controller_profiles"]:
        controller = SNAPSHOT["controller_profiles"][controller_type]
        for bits in product((False, True), repeat=len(FEATURE_ORDER)):
            features = _feature_state(bits)
            payload = build_publication_payload(_profile(controller_type, bits))
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            publication.content_json = encoded
            publication.content_sha256 = hashlib.sha256(encoded.encode()).hexdigest()
            db.commit()
            expected_codes = set(_expected_codes(features))
            for section, heading in SNAPSHOT["sections"].items():
                response = client.get(f"/api/v1/governance/public/{section}.html")
                assert response.status_code == 200, (controller_type, bits, section)
                body = response.text
                assert f"<h1>{heading}</h1>" in body
                if section in {"privacy", "legal"}:
                    assert html.escape(controller["controller_legal_name"], quote=True) in body
                if section == "privacy":
                    for code, text in catalog.items():
                        assert (html.escape(text, quote=True) in body) is (code in expected_codes), (controller_type, bits, code)
                    assert ("Optional IndexedDB offline calendar" in body) is features["offline_schedule_enabled"]
                if section == "processors":
                    assert "Synthetic VPS hosting" in body
                    assert ("Synthetic SMTP delivery" in body) is features["smtp_enabled"]
                    assert ("Synthetic Push delivery" in body) is features["push_enabled"]
                    assert ("Synthetic Support access" in body) is features["external_support_enabled"]
                rendered += 1
    assert rendered == 896
    assert client.get("/api/v1/governance/public/not-a-section.html").status_code == 404


def test_runtime_conditioned_preflight_accepts_truth_and_rejects_mismatch(monkeypatch):
    for smtp, push, ha in product((False, True), repeat=3):
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.synthetic.invalid" if smtp else "")
        monkeypatch.setattr(settings, "SMTP_USERNAME", "synthetic" if smtp else "")
        monkeypatch.setattr(settings, "SMTP_TOKEN", "synthetic-token" if smtp else "")
        monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "sender@synthetic.invalid" if smtp else "")
        monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "synthetic-private-key" if push else "")
        monkeypatch.setattr(settings, "VAPID_CLAIMS_EMAIL", "push@synthetic.invalid" if push else "")
        monkeypatch.setattr(settings, "HA_MODE", "ha" if ha else "standalone")
        bits = (smtp, push, False, False, False, ha)
        assert governance_preflight(_profile("organisation", bits))["ready"] is True
        mismatched = _profile("organisation", (not smtp, push, False, False, False, ha))
        checks = governance_preflight(mismatched)["checks"]
        assert any(item["code"] == "smtp_enabled" and item["status"] == "contradiction" for item in checks)
