"""Independent Phase E portable bundle and optional Git archive contracts."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from repo_roots import optional_docs_root, server_root


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = server_root()
DOCS_ROOT = optional_docs_root()
project_site_required = pytest.mark.skipif(
    DOCS_ROOT is None,
    reason="project-site contracts require an explicit valid MP_OPT_DOCS_ROOT",
)


def test_bundle_first_integrated_uploader_interfaces_are_complete():
    required = (
        "deploy/evidence/portable_bundle.py",
        "deploy/evidence/evidence_archive_repository.py",
        "deploy/evidence/evidence_git_uploader.py",
        "deploy/evidence/github_token_client.py",
        "deploy/evidence/git-template/README.md",
        "deploy/evidence/git-template/CODEOWNERS",
        "deploy/evidence/git-template/.github/workflows/verify-evidence.yml",
        "tools/verify_evidence_repo.py",
        "tools/validate_ingestion_paths.py",
        "docs/evidence/controller-evidence-git.md",
        "docs/evidence/human-readable-evidence.md",
    )
    assert all((SERVER_ROOT / path).is_file() for path in required)
    bundle = (SERVER_ROOT / required[0]).read_text(encoding="utf-8")
    uploader = (SERVER_ROOT / required[2]).read_text(encoding="utf-8")
    assert "deterministic, self-contained" in bundle
    assert "never executed by the integrated Server uploader" in bundle
    assert "awaiting_checks" in uploader and "awaiting_merge" in uploader
    assert "pull_request_head_sha" in uploader and "delete_branch" in uploader


def test_fine_grained_token_is_the_only_authentication_mode_and_is_bounded():
    client = (SERVER_ROOT / "deploy/evidence/github_token_client.py").read_text(encoding="utf-8")
    tui = (SERVER_ROOT / "deploy/management/evidence.sh").read_text(encoding="utf-8")
    compose = (SERVER_ROOT / "infra/docker-compose.prod.yml").read_text(encoding="utf-8")
    combined = "\n".join((client, tui, compose))
    assert "Fine-grained GitHub personal access token" in tui
    assert "github_pat_" in client and "github_pat_*" in tui
    assert "ui_password" in tui and "--token-file" in tui
    assert "EVIDENCE_GIT_ARCHIVE_ENABLED: bool = False" in (
        SERVER_ROOT / "backend/app/core/config.py"
    ).read_text(encoding="utf-8")
    for obsolete in (
        "github_app", "app_id", "installation_id", "installation_token",
        "app_private_key", "generate_jwt",
    ):
        assert obsolete not in combined.casefold()
    assert "Evidence-Public" in tui


def test_archive_template_requires_exact_verification_and_ingestion_checks():
    workflow = (
        SERVER_ROOT / "deploy/evidence/git-template/.github/workflows/verify-evidence.yml"
    ).read_text(encoding="utf-8")
    verifier = (
        SERVER_ROOT / "deploy/evidence/evidence_archive_repository.py"
    ).read_text(encoding="utf-8")
    client = (SERVER_ROOT / "deploy/evidence/github_token_client.py").read_text(encoding="utf-8")
    assert "name: Evidence verification" in workflow
    assert "name: Ingestion path validation" in workflow
    assert "contents: read" in workflow
    assert "add exactly two files" in verifier
    assert "evidence.bundle" in verifier and "bundle.sha256" in verifier
    assert "pull_request_head_changed" in client
    assert "expected_head_sha" in client


def test_synthetic_regressions_cover_token_secrecy_retry_and_portable_tamper():
    tests = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SERVER_ROOT / "server_backend/test_evidence_git.py",
            SERVER_ROOT / "server_backend/test_evidence_git_uploader.py",
        )
    )
    for case in (
        "deterministic_self_contained",
        "tamper_binding_and_path_traversal",
        "token_readiness_is_private_bound_and_never_disclosed",
        "invalid_expired_and_insufficient_tokens",
        "evidence_public_is_never",
        "monitors_exact_sha_merges_and_cleans_branch",
        "transient_merge_retry_preserves_pull_request",
        "masked_atomic_secret_storage",
    ):
        assert case in tests


@project_site_required
def test_public_documentation_states_custody_permissions_and_verification_limits():
    server_doc = (
        SERVER_ROOT / "docs/evidence/controller-evidence-git.md"
    ).read_text(encoding="utf-8")
    public_doc = (
        DOCS_ROOT / "src/app/docs/advanced/accountability-evidence/page.tsx"
    ).read_text(encoding="utf-8")
    for text in (server_doc, public_doc):
        assert "Fine-grained GitHub personal access token" in text
        assert "disabled by default" in text
        assert "Evidence verification" in text
        assert "Ingestion path validation" in text
        assert "does not prove physical deletion" in text
        assert "legal compliance" in text
    assert "Each deployment has its own controller and generated privacy notice" in public_doc
    assert "are not inferred by the software" in public_doc
