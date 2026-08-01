"""Independent cross-repository contracts for role-separated signed evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from app.core.operator_evidence import (
    TRUST_NAMESPACE,
    key_id,
    validate_registration_document,
    verify_signature,
)
from repo_roots import app_root, server_root


APP_ROOT = app_root()
SERVER_ROOT = server_root()


def _processor_package(app_root: Path) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    script = textwrap.dedent(
        f"""
        import base64
        import hashlib
        import json
        import uuid
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.operator_evidence import action_payload, canonical_json, generate_key, sign_document
        from app.core.secure_credentials import set_credential_store_for_tests
        from app.models.operator_evidence import ProcessorEvidenceKey

        class MemoryStore:
            def __init__(self): self.values = {{}}
            def available(self): return True
            def get(self, account): return self.values.get(account)
            def set(self, account, value): self.values[account] = value
            def delete(self, account): self.values.pop(account, None)

        engine = create_engine('sqlite:///:memory:')
        ProcessorEvidenceKey.__table__.create(bind=engine)
        db = sessionmaker(bind=engine)()
        store = MemoryStore()
        set_credential_store_for_tests(store)
        row = generate_key(db, processor_id='prc-syntheticprocessor')
        challenge = {{
            'format': 'mp-opt-trust-key-registration-v1',
            'challenge_id': str(uuid.uuid4()),
            'action': 'register',
            'instance_id': str(uuid.uuid4()),
            'entity_id': row.processor_id,
            'key_id': row.key_id,
            'role': 'processor',
            'algorithm': 'Ed25519',
            'public_key_sha256': row.public_key_sha256,
            'supersedes_key_id': None,
            'reason': None,
            'action_sha256': '',
            'nonce': base64.b64encode(b'x' * 32).decode('ascii'),
            'created_at': '{now.strftime('%Y-%m-%dT%H:%M:%SZ')}',
            'expires_at': '{(now + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')}',
        }}
        challenge['action_sha256'] = hashlib.sha256(canonical_json(action_payload(challenge))).hexdigest()
        proof = sign_document(db, identifier=row.key_id, document=challenge, kind='registration')
        print(json.dumps({{
            'public_key': row.public_key,
            'key_id': row.key_id,
            'challenge': challenge,
            'proof': proof,
            'sqlite_columns': [column.name for column in ProcessorEvidenceKey.__table__.columns],
            'keyring_accounts': sorted(store.values),
            'private_marker_in_output': 'PRIVATE KEY' in json.dumps({{
                'public_key': row.public_key, 'challenge': challenge, 'proof': proof,
            }}),
        }}, sort_keys=True))
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


def test_desktop_processor_proof_matches_server_protocol_without_private_key_transfer():
    package = _processor_package(APP_ROOT)

    validate_registration_document(package["challenge"])
    digest = verify_signature(package["challenge"], package["proof"], package["public_key"])

    assert len(digest) == 64
    assert package["key_id"] == key_id(package["public_key"])
    assert package["proof"]["namespace"] == TRUST_NAMESPACE
    assert package["challenge"]["role"] == "processor"
    assert package["private_marker_in_output"] is False
    assert all("private" not in column for column in package["sqlite_columns"])
    assert package["keyring_accounts"] == [
        f"masterplan:processor-key:{package['key_id']}:private-ed25519-pkcs8"
    ]


def test_git_anchor_is_controller_only_and_has_no_generic_operator_interface():
    repository_source = (
        SERVER_ROOT / "deploy/evidence/evidence_repository.py"
    ).read_text(encoding="utf-8")
    helper_source = (
        SERVER_ROOT / "deploy/evidence/evidence_repo.py"
    ).read_text(encoding="utf-8")

    assert 'CONTROLLER_ROLE = "controller"' in repository_source
    assert 'ANCHOR_FORMAT = "mp-opt-git-anchor-v2"' in repository_source
    assert '"controller_key_id": controller_key_id' in repository_source
    assert '"controller_role": CONTROLLER_ROLE' in repository_source
    assert "--controller-key-id" in repository_source and "--controller-key-id" in helper_source
    for forbidden in ("ALLOWED_OPERATOR_ROLES", "--operator-key-id", "--operator-role"):
        assert forbidden not in repository_source
        assert forbidden not in helper_source


def test_private_repository_ci_and_workstation_commands_cover_archive_boundary():
    workflow = (
        SERVER_ROOT / "deploy/evidence/repository-template/.github/workflows/verify-evidence.yml"
    ).read_text(encoding="utf-8")
    helper = (SERVER_ROOT / "deploy/evidence/evidence_repo.py").read_text(encoding="utf-8")

    assert "push:" in workflow and "pull_request:" in workflow
    assert "verify --archive ." in workflow
    for command in ("initialise", "verify", "import-bundle", "commit", "push", "create-anchor"):
        assert f'add_parser("{command}")' in helper
    assert '"commit", "-S"' in helper
    assert "--force" not in helper
    assert "private_key" not in helper


@pytest.mark.parametrize("forbidden", ["person_name", "email", "task_title", "schedule_data", "private_key"])
def test_evidence_schema_has_no_personal_or_private_fields(forbidden: str):
    schema = (SERVER_ROOT / "deploy/evidence/evidence_manifest.py").read_text(encoding="utf-8")
    payload_block = schema.split("PAYLOAD_FIELDS =", 1)[1].split("UUID_FIELDS =", 1)[0]
    assert f'"{forbidden}"' not in payload_block
