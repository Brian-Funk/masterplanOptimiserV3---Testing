"""Independent Phase 6 licence and publication-readiness contracts."""

import hashlib
import json
import os
from pathlib import Path
import tomllib

from repo_roots import app_root, server_root


EYP_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = server_root()
APP_ROOT = app_root()
TESTING_ROOT = Path(__file__).resolve().parents[1]
AGPL_SHA256 = "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"


def _normalised_sha(path: Path) -> str:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(content.encode()).hexdigest()


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_publication_repositories_use_exact_agpl_and_spdx_metadata():
    for root in (SERVER_ROOT, APP_ROOT, TESTING_ROOT):
        assert _normalised_sha(root / "LICENSE") == AGPL_SHA256
        for required in (
            "BRANDING.md",
            "CONTRIBUTING.md",
            "COPYRIGHT-AND-CONTRIBUTION-PROVENANCE.md",
            "THIRD-PARTY-NOTICES.md",
        ):
            assert (root / required).is_file()

    assert tomllib.loads((SERVER_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["license"] == "AGPL-3.0-only"
    assert tomllib.loads((APP_ROOT / "compute/pyproject.toml").read_text(encoding="utf-8"))["project"]["license"] == "AGPL-3.0-only"
    assert tomllib.loads((TESTING_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["license"] == "AGPL-3.0-only"
    for path in (
        SERVER_ROOT / "web/package.json",
        SERVER_ROOT / "infra/cloudflare-ha-witness/package.json",
        APP_ROOT / "web/package.json",
        APP_ROOT / "desktop/package.json",
        TESTING_ROOT / "package.json",
    ):
        assert _json(path)["license"] == "AGPL-3.0-only"


def test_generated_notices_cover_locked_dependencies_and_in_app_copies():
    server_notice = (SERVER_ROOT / "THIRD-PARTY-NOTICES.md").read_bytes()
    app_notice = (APP_ROOT / "THIRD-PARTY-NOTICES.md").read_bytes()
    assert server_notice == (SERVER_ROOT / "web/legal-artifacts/THIRD-PARTY-NOTICES.md").read_bytes()
    assert app_notice == (APP_ROOT / "web/legal-artifacts/THIRD-PARTY-NOTICES.md").read_bytes()
    assert (SERVER_ROOT / "LICENSE").read_bytes() == (SERVER_ROOT / "web/legal-artifacts/LICENSE").read_bytes()
    assert (APP_ROOT / "LICENSE").read_bytes() == (APP_ROOT / "web/legal-artifacts/LICENSE").read_bytes()
    assert server_notice.count(b"\n|") > 700
    assert app_notice.count(b"\n|") > 650
    assert (TESTING_ROOT / "THIRD-PARTY-NOTICES.md").read_bytes().count(b"\n|") > 200


def test_corresponding_source_is_exact_and_modified_builds_are_supported():
    for root in (SERVER_ROOT, APP_ROOT):
        resolver = (root / "web/source-identity.cjs").read_text(encoding="utf-8")
        config = (root / "web/next.config.js").read_text(encoding="utf-8")
        assert "^[0-9a-f]{40}$" in resolver
        assert "credential-free HTTPS" in resolver
        for variable in (
            "MP_PUBLIC_SOURCE_REPOSITORY_URL",
            "MP_PUBLIC_SOURCE_REVISION",
            "MP_PUBLIC_SOURCE_URL",
        ):
            assert variable in resolver
        assert "NEXT_PUBLIC_SOURCE_URL" in config

    server_release = (SERVER_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    app_release = (APP_ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "MP_PUBLIC_SOURCE_REVISION: ${{ steps.release.outputs.release_commit }}" in server_release
    assert "MP_PUBLIC_SOURCE_REVISION: ${{ needs.preflight.outputs.release_commit || github.sha }}" in app_release
    assert "Corresponding source" in (APP_ROOT / "web/src/app/dashboard/layout.tsx").read_text(encoding="utf-8")


def test_private_notes_are_absent_and_fresh_history_is_mandatory():
    for forbidden in (
        "CODEX_PROGRESS.md",
        "FINAL_VALIDATION_REPORT.md",
        "GDPR_TECHNICAL_REPORT.md",
        "MIGRATION_REPORT.md",
        "SECURITY_REPORT.md",
    ):
        assert not (SERVER_ROOT / forbidden).exists()
    assert not (APP_ROOT / "notes").exists()
    assert not (APP_ROOT / "optimisation-debug.txt").exists()
    assert "publication_audit.py --history" in (SERVER_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "audit:publication:history" in (APP_ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    for runbook in (
        SERVER_ROOT / "docs/publication-runbook.md",
        APP_ROOT / "docs/publication-runbook.md",
    ):
        text = runbook.read_text(encoding="utf-8").lower()
        assert all(term in text for term in ("parentless", "root", "commit"))
        assert "do not change" in text and "visibility in place" in text


def test_branding_is_separate_and_provenance_stays_explicitly_human_gated():
    for root in (SERVER_ROOT, APP_ROOT, TESTING_ROOT):
        branding = (root / "BRANDING.md").read_text(encoding="utf-8")
        provenance = (root / "COPYRIGHT-AND-CONTRIBUTION-PROVENANCE.md").read_text(encoding="utf-8")
        assert "separate from the GNU Affero General Public License" in branding
        assert "does not alter, narrow or condition" in branding
        assert "must" in provenance and "confirm" in provenance
