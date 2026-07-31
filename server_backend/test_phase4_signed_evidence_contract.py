"""Independent cross-repository contracts for Phase 4 signed evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from app.core.operator_evidence import (
    GIT_ANCHOR_ROLES,
    OPERATOR_NAMESPACE,
    key_id,
    validate_registration_document,
    verify_signature,
)


EYP_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = Path(os.environ.get(
    "MP_OPT_APP_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - App" / "masterplanOptimiserV3 - App",
))
SERVER_ROOT = Path(os.environ.get(
    "MP_OPT_SERVER_ROOT",
    EYP_ROOT / "MasterplanOptimiserV3 - Server" / "MasterplanOptimiserV3---Server",
))


def _desktop_package(app_root: Path) -> dict:
    script = textwrap.dedent(
        """
        import base64
        from datetime import datetime, timedelta, timezone
        import json
        import uuid
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.operator_evidence import generate_key, sign_document
        from app.core.secure_credentials import set_credential_store_for_tests
        from app.db.database import Base
        from app.models.operator_evidence import OperatorEvidenceKey

        class MemoryStore:
            def __init__(self): self.values = {}
            def available(self): return True
            def get(self, account): return self.values.get(account)
            def set(self, account, value): self.values[account] = value
            def delete(self, account): self.values.pop(account, None)

        engine = create_engine('sqlite:///:memory:')
        OperatorEvidenceKey.__table__.create(bind=engine)
        db = sessionmaker(bind=engine)()
        store = MemoryStore()
        set_credential_store_for_tests(store)
        row = generate_key(db, role='desktop_operator')
        now = datetime.now(timezone.utc).replace(microsecond=0)
        challenge = {
            'format': 'mp-opt-operator-key-registration-v1',
            'challenge_id': str(uuid.uuid4()),
            'purpose': 'register',
            'instance_id': str(uuid.uuid4()),
            'key_id': row.key_id,
            'public_key_sha256': row.public_key_sha256,
            'role': row.role,
            'supersedes_key_id': None,
            'rotation_reason': None,
            'nonce': base64.b64encode(b'x' * 32).decode('ascii'),
            'created_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_at': (now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        proof = sign_document(db, identifier=row.key_id, document=challenge, kind='registration')
        print(json.dumps({
            'public_key': row.public_key,
            'key_id': row.key_id,
            'challenge': challenge,
            'proof': proof,
            'sqlite_columns': [column.name for column in OperatorEvidenceKey.__table__.columns],
            'keyring_accounts': sorted(store.values),
            'private_marker_in_output': 'PRIVATE KEY' in json.dumps({
                'public_key': row.public_key, 'challenge': challenge, 'proof': proof,
            }),
        }, sort_keys=True))
        """
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=app_root / "backend",
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_desktop_generated_proof_matches_server_protocol_without_private_key_transfer():
    package = _desktop_package(APP_ROOT)

    validate_registration_document(package["challenge"])
    digest = verify_signature(package["challenge"], package["proof"], package["public_key"])

    assert len(digest) == 64
    assert package["key_id"] == key_id(package["public_key"])
    assert package["proof"]["namespace"] == OPERATOR_NAMESPACE
    assert package["private_marker_in_output"] is False
    assert all("private" not in column for column in package["sqlite_columns"])
    assert package["keyring_accounts"] == [
        f"masterplan:evidence-key:{package['key_id']}:private-ed25519-pkcs8"
    ]


def test_git_anchor_role_scope_is_identical_across_server_desktop_and_repository_helper():
    desktop_source = (APP_ROOT / "backend/app/core/operator_evidence.py").read_text(encoding="utf-8")
    repository_source = (SERVER_ROOT / "deploy/evidence/evidence_repository.py").read_text(encoding="utf-8")

    assert GIT_ANCHOR_ROLES == {"controller", "root_operator", "evidence_auditor"}
    for role in GIT_ANCHOR_ROLES:
        assert role in desktop_source
        assert role in repository_source
    assert 'GIT_ANCHOR_ROLES = frozenset({"controller", "root_operator", "evidence_auditor"})' in desktop_source
    assert 'ALLOWED_OPERATOR_ROLES = {"controller", "root_operator", "evidence_auditor"}' in repository_source


def test_private_repository_ci_and_workstation_commands_cover_every_phase4_boundary():
    workflow = (
        SERVER_ROOT / "deploy/evidence/repository-template/.github/workflows/verify-evidence.yml"
    ).read_text(encoding="utf-8")
    helper = (SERVER_ROOT / "deploy/evidence/evidence_repo.py").read_text(encoding="utf-8")
    api = (SERVER_ROOT / "backend/app/api/v1/evidence_keys.py").read_text(encoding="utf-8")

    assert "push:" in workflow and "pull_request:" in workflow
    assert "verify --archive ." in workflow
    for command in ("initialise", "verify", "import-bundle", "commit", "push", "create-anchor"):
        assert f'add_parser("{command}")' in helper
    assert '"commit", "-S"' in helper
    assert "--force" not in helper
    assert "git-anchors/import" in api
    assert "private_key" not in api


@pytest.mark.parametrize("forbidden", ["person_name", "email", "task_title", "schedule_data", "private_key"])
def test_evidence_schema_has_no_personal_or_private_fields(forbidden: str):
    schema = (SERVER_ROOT / "deploy/evidence/evidence_manifest.py").read_text(encoding="utf-8")
    payload_block = schema.split("PAYLOAD_FIELDS =", 1)[1].split("UUID_FIELDS =", 1)[0]
    assert f'"{forbidden}"' not in payload_block
