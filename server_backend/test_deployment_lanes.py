"""Contracts for fast exact-commit testing and immutable signed releases."""

from __future__ import annotations

import stat
from pathlib import Path


ROOT = (
    Path(__file__).resolve().parents[3]
    / "MasterplanOptimiserV3 - Server"
    / "MasterplanOptimiserV3---Server"
)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_unsigned_lane_is_exact_commit_and_root_policy_gated() -> None:
    supervisor = ROOT / "deploy/test-deployment.sh"
    source = supervisor.read_text(encoding="utf-8")
    assert supervisor.stat().st_mode & stat.S_IXUSR
    assert "require_test_policy" in source
    assert "deployment-policy" in text("deploy/management/common.sh")
    assert "exact 40-character commit" in source
    assert "git clone --filter=blob:none --no-checkout" in source
    assert "git -C \"$MP_TEST_SOURCE\" fetch --no-tags --force origin \"$commit\"" in source
    assert "MP-OPT UNSIGNED TEST BUILD DEPLOYED" in source


def test_signed_lane_is_exact_tag_peer_first_and_immutable() -> None:
    supervisor = ROOT / "deploy/signed-deployment.sh"
    source = supervisor.read_text(encoding="utf-8")
    workflow = text(".github/workflows/release.yml")
    assert supervisor.stat().st_mode & stat.S_IXUSR
    assert "validate tag" in source
    assert "MP_SIGNED_PEER=1" in source
    assert "--tag \"$tag\"" in source
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow.split("permissions:", 1)[0]
    assert "retired-tags.txt" in workflow
    assert "gh release create \"$TAG\"" in workflow
    assert "gh release delete" not in workflow


def test_ci_is_draft_aware_and_uses_shared_component_classifier() -> None:
    workflow = text(".github/workflows/server-ci.yml")
    assert "github.event.pull_request.draft == false" in workflow
    assert "Draft PR: heavy CI intentionally deferred." in workflow
    assert "deploy/test_deployment.py classify" in workflow
    assert "server-ci-result" in workflow


def test_retired_release_name_cannot_be_reused() -> None:
    retired = {
        line.strip()
        for line in text("deploy/release/retired-tags.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "v3.4.0" in retired
